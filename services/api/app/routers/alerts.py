from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_store
from app.models import AlertSubscription, AlertSubscriptionIn
from app.store import SubscriptionStore

router = APIRouter(prefix="/v1/alerts", tags=["alerts"])


@router.post("/subscriptions", response_model=AlertSubscription, status_code=201)
async def subscribe(body: AlertSubscriptionIn, store: SubscriptionStore = Depends(get_store)):
    return store.add(body)


@router.get("/subscriptions", response_model=list[AlertSubscription])
async def list_subscriptions(store: SubscriptionStore = Depends(get_store)):
    return store.all()


@router.delete("/subscriptions/{sub_id}", status_code=204)
async def unsubscribe(sub_id: str, store: SubscriptionStore = Depends(get_store)):
    if not store.remove(sub_id):
        raise HTTPException(404, "Subscription not found")
