from app.services.knowledge import KnowledgeService, sales_knowledge


def test_sales_knowledge_loads_playbooks():
    playbooks = sales_knowledge.list_playbooks()
    assert "EmailFrameworks.md" in playbooks
    assert "SignalPlaybook.md" in playbooks
    assert "LeadQualification.md" in playbooks
    assert "ObjectionHandling.md" in playbooks
    assert "FollowupStrategy.md" in playbooks
    assert "OfferStrategy.md" in playbooks


def test_sales_knowledge_content():
    frameworks = sales_knowledge.get_email_frameworks()
    assert "Mockup-Led" in frameworks
    assert "Audit-Led" in frameworks
    assert "Research-Led" in frameworks

    banned = sales_knowledge.get_banned_words()
    assert "game-changer" in banned
    assert "synergy" in banned

    prompt_ctx = sales_knowledge.format_framework_context("mockup_led")
    assert "MOCKUP_LED" in prompt_ctx
    assert "BANNED WORDS" in prompt_ctx
