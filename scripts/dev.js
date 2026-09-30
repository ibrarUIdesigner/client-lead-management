const { spawn } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const isWin = process.platform === "win32";

function run(name, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    stdio: ["ignore", "pipe", "pipe"],
    shell: isWin,
    env: process.env,
  });

  const prefix = (stream) => {
    stream.on("data", (chunk) => {
      const lines = chunk.toString().split(/\r?\n/);
      for (const line of lines) {
        if (line.length) process.stdout.write(`[${name}] ${line}\n`);
      }
    });
  };

  prefix(child.stdout);
  prefix(child.stderr);

  child.on("exit", (code, signal) => {
    const reason = signal ? `signal ${signal}` : `code ${code ?? 0}`;
    process.stdout.write(`[${name}] exited with ${reason}\n`);
    shutdown(code ?? 1);
  });

  return child;
}

const children = [];
let shuttingDown = false;

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) {
      if (isWin) {
        spawn("taskkill", ["/pid", String(child.pid), "/f", "/t"], {
          stdio: "ignore",
          shell: true,
        });
      } else {
        child.kill("SIGTERM");
      }
    }
  }
  setTimeout(() => process.exit(code), 300).unref();
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

children.push(
  run(
    "backend",
    ".venv\\Scripts\\python.exe",
    ["-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
    path.join(root, "backend"),
  ),
);

children.push(
  run("frontend", isWin ? "npm.cmd" : "npm", ["run", "dev"], path.join(root, "frontend")),
);
