import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.deps import rate_limit, require_member
from app.models import Conversation, Feedback, Message, User
from app.rag.answer import answer_stream
from app.schemas.common import ChatIn, ConversationDetail, ConversationOut, ConversationRename, FeedbackIn, MessageOut, Page

router = APIRouter(prefix="/chat", tags=["chat"])


def _own_conversation(db: Session, cid: int, user: User) -> Conversation:
    c = db.get(Conversation, cid)
    if not c or c.user_id != user.id:  # chat history is private to its owner
        raise HTTPException(404, "Conversation not found")
    return c


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(
    q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100),
    user: User = Depends(require_member), db: Session = Depends(get_db),
):
    stmt = select(Conversation).where(Conversation.user_id == user.id)
    snippets: dict[int, str] = {}
    if q:
        matching = select(Message.conversation_id).where(Message.content.ilike(f"%{q}%"))
        stmt = stmt.where(or_(Conversation.title.ilike(f"%{q}%"), Conversation.id.in_(matching)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    convs = db.scalars(stmt.order_by(Conversation.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    if q and convs:
        for m in db.scalars(select(Message).where(Message.conversation_id.in_([c.id for c in convs]), Message.content.ilike(f"%{q}%")).order_by(Message.id)):
            if m.conversation_id not in snippets:
                i = m.content.lower().find(q.lower())
                snippets[m.conversation_id] = ("…" if i > 40 else "") + m.content[max(0, i - 40): i + 80] + "…"
    return Page(
        items=[ConversationOut.model_validate(c).model_copy(update={"snippet": snippets.get(c.id)}) for c in convs],
        total=total, page=page, page_size=page_size,
    )


@router.get("/conversations/{cid}", response_model=ConversationDetail)
def get_conversation(cid: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    c = _own_conversation(db, cid, user)
    fb = dict(db.execute(select(Feedback.message_id, Feedback.helpful).join(Message).where(Message.conversation_id == cid, Feedback.user_id == user.id)).all())
    msgs = [MessageOut.model_validate(m).model_copy(update={"feedback": fb.get(m.id)}) for m in c.messages]
    return ConversationDetail(**ConversationOut.model_validate(c).model_dump(), messages=msgs)


@router.patch("/conversations/{cid}", response_model=ConversationOut)
def rename_conversation(cid: int, body: ConversationRename, user: User = Depends(require_member), db: Session = Depends(get_db)):
    c = _own_conversation(db, cid, user)
    c.title = body.title.strip()
    db.commit()
    return ConversationOut.model_validate(c)


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: int, user: User = Depends(require_member), db: Session = Depends(get_db)):
    db.delete(_own_conversation(db, cid, user))
    db.commit()


@router.post("/stream")
def chat_stream(body: ChatIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    """Streams the answer as Server-Sent Events: meta, status, sources, token..., done | error."""
    rate_limit("chat", get_settings().chat_rate_limit_per_minute, 60, str(user.id))
    if not body.regenerate and not body.message.strip():
        raise HTTPException(400, "Message is empty")
    if body.conversation_id:
        conv = _own_conversation(db, body.conversation_id, user)
        conv_id = conv.id
    else:
        conv = Conversation(user_id=user.id, language=body.language, is_voice=body.is_voice)
        db.add(conv)
        db.commit()
        conv_id = conv.id
    user_id = user.id

    def events():
        session = SessionLocal()  # generator outlives the request-scoped session
        try:
            u = session.get(User, user_id)
            c = session.get(Conversation, conv_id)
            for event in answer_stream(session, u, c, body.message, body.language, web=body.web, regenerate=body.regenerate):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as exc:  # never leak internals into the stream
            import logging

            logging.getLogger(__name__).exception("Chat stream failed")
            session.rollback()
            yield f"data: {json.dumps({'type': 'error', 'message': 'BUI hit an internal error while answering. Please try again.'})}\n\n"
            del exc
        finally:
            session.close()

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/messages/{message_id}/feedback", status_code=204)
def feedback(message_id: int, body: FeedbackIn, user: User = Depends(require_member), db: Session = Depends(get_db)):
    m = db.get(Message, message_id)
    if not m or m.role != "assistant" or m.conversation.user_id != user.id:
        raise HTTPException(404, "Message not found")
    fb = db.scalar(select(Feedback).where(Feedback.message_id == message_id, Feedback.user_id == user.id))
    if fb is None:
        fb = Feedback(message_id=message_id, user_id=user.id, helpful=body.helpful)
        db.add(fb)
    fb.helpful = body.helpful
    fb.comment = body.comment
    db.commit()


@router.get("/suggestions")
def suggestions(user: User = Depends(require_member), db: Session = Depends(get_db)):
    """Starter prompts for the chat home screen, personalised with real product names."""
    from app.models import Product

    names = db.scalars(select(Product.name).where(Product.status == "verified").order_by(Product.updated_at.desc()).limit(2)).all()
    a = names[0] if names else "Product A"
    b = names[1] if len(names) > 1 else "Product B"
    return [
        {"icon": "list", "title": "Find product specifications", "prompt": f"What are the specifications of {a}?"},
        {"icon": "git-compare", "title": "Compare two products", "prompt": f"What is the difference between {a} and {b}?"},
        {"icon": "sparkles", "title": "Explain product features", "prompt": f"What are the key features and advantages of {a}?"},
        {"icon": "wrench", "title": "Find installation instructions", "prompt": f"How do I install {a}?"},
        {"icon": "shield-check", "title": "Check warranty details", "prompt": f"What is the warranty period for {a}?"},
        {"icon": "globe", "title": "Research a new product", "prompt": "Research online: ", "web": True},
    ]
