import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { MarkdownView } from "../features/design-md/markdown";
import {
  useDesignGuide,
  useDesignGuideTemplate,
  useSaveDesignGuide,
  useUploadDesignGuide,
} from "../hooks/useDesignGuides";
import { apiErrorMessage } from "../lib/apiError";

const defaultMaxBytes = 262144;

export function DesignGuideEditorPage() {
  const { guideId } = useParams();
  const isNew = !guideId;
  const existing = useDesignGuide(guideId);
  const template = useDesignGuideTemplate(isNew);
  const save = useSaveDesignGuide(guideId);
  const upload = useUploadDesignGuide();
  const navigate = useNavigate();
  const { notify } = useToast();

  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tags, setTags] = useState("");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadKey = guideId ?? (template.data ? "template" : null);
  if (loadKey && loadKey !== loadedKey) {
    if (guideId && existing.data) {
      setLoadedKey(guideId);
      setName(existing.data.name);
      setDescription(existing.data.description ?? "");
      setTags(existing.data.tags.join(", "));
      setContent(existing.data.content);
    } else if (!guideId && template.data) {
      setLoadedKey("template");
      setContent(template.data);
    }
  }

  const pending = isNew ? template.isPending : existing.isPending;
  const loadError = isNew ? template.error : existing.error;

  async function onFile(next: File | null) {
    setFile(null);
    setError(null);
    if (!next) {
      return;
    }
    if (!next.name.toLowerCase().endsWith(".md")) {
      setError("Upload a file that ends in .md.");
      return;
    }
    if (next.size > defaultMaxBytes) {
      setError(`That file is larger than ${defaultMaxBytes} bytes.`);
      return;
    }
    const text = await next.text();
    if (!text.trim()) {
      setError("The Markdown file is empty.");
      return;
    }
    setFile(next);
    setContent(text);
  }

  async function onSubmit() {
    setError(null);
    if (!name.trim()) {
      setError("Enter a name.");
      return;
    }
    if (!content.trim()) {
      setError("Enter the design guide.");
      return;
    }
    const tagList = tags
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    try {
      if (isNew && file && (await file.text()) === content) {
        const form = new FormData();
        form.set("name", name.trim());
        if (description.trim()) {
          form.set("description", description.trim());
        }
        form.set("tags", tagList.join(", "));
        form.set("file", file);
        const created = await upload.mutateAsync(form);
        notify("Design guide created.", "success");
        navigate(`/design-md/${created.id}`);
        return;
      }
      const saved = await save.mutateAsync({
        name: name.trim(),
        description: description.trim() || null,
        tags: tagList,
        content,
      });
      notify(isNew ? "Design guide created." : "Design guide saved.", "success");
      navigate(`/design-md/${saved.id}`);
    } catch (caught) {
      setError(apiErrorMessage(caught, "The design guide could not be saved."));
    }
  }

  return (
    <>
      <PageHeader
        title={isNew ? "New design guide" : "Edit design guide"}
        description="Write visual direction in Markdown. HTML is shown as text and is not run."
        actions={
          <Link to={guideId ? `/design-md/${guideId}` : "/design-md"} className="text-body text-primary-700">
            Cancel
          </Link>
        }
      />
      <QueryGate
        pending={pending}
        error={loadError}
        fallback="The design guide could not be loaded."
        onRetry={() => {
          void (isNew ? template.refetch() : existing.refetch());
        }}
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="space-y-4">
            <Input label="Name" value={name} onChange={(event) => setName(event.target.value)} />
            <Input
              label="Description"
              hint="Optional. What this guide is for."
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
            <Input
              label="Tags"
              hint="Comma-separated, such as calm, clinic."
              value={tags}
              onChange={(event) => setTags(event.target.value)}
            />
            <label className="flex flex-col gap-2 text-small font-medium text-gray-700">
              Markdown file
              <input
                type="file"
                accept=".md,text/markdown"
                className="text-body font-normal"
                onChange={(event) => {
                  void onFile(event.target.files?.[0] ?? null);
                }}
              />
              <span className="font-normal text-gray-500">
                Optional .md upload, up to {defaultMaxBytes} bytes unless the server limit differs.
              </span>
            </label>
            <Textarea
              label="Markdown"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="min-h-96 font-mono"
            />
            {error ? (
              <p className="text-small text-danger" role="alert">
                {error}
              </p>
            ) : null}
            <Button onClick={() => void onSubmit()} isLoading={save.isPending || upload.isPending}>
              Save
            </Button>
          </Card>
          <Card>
            <h2 className="text-h4 font-semibold text-ink">Preview</h2>
            <div className="mt-4">
              <MarkdownView source={content} />
            </div>
          </Card>
        </div>
      </QueryGate>
    </>
  );
}
