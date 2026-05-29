from app.models import TaskType, XPost, XUser


def public_reply_suggestions(user: XUser, post: XPost | None) -> str:
    context = (post.text if post else user.bio).strip()
    context = context[:220]
    return "\n".join(
        [
            f"1. @{user.username} this is a useful framing. The privacy tradeoff I would add is threat model first, then tool choice.",
            f"2. @{user.username} agreed on the core concern here. Have you seen teams handle this with a zero-knowledge default?",
            f"3. @{user.username} sharp point. The practical question may be how to make the safer path the easiest path for non-experts.",
            f"\nContext used: {context}",
        ]
    )


def dm_draft(user: XUser, post: XPost | None) -> str:
    anchor = f"your post about \"{post.text[:120]}\"" if post else "your recent privacy/security posts"
    return (
        f"Hi {user.name or user.username}, I saw {anchor}. "
        "You mentioned being open to contact, so I wanted to share a concise idea that may be relevant. "
        "We are mapping privacy/security workflows for people comparing tools like Signal, Proton, and E2EE products, "
        "and your perspective looked especially useful. No pressure at all, and if you prefer not to hear from me again, "
        "just reply stop and I will not follow up."
    )


def draft_for_task(task_type: TaskType, user: XUser, post: XPost | None) -> str:
    if task_type == TaskType.dm_draft:
        return dm_draft(user, post)
    return public_reply_suggestions(user, post)

