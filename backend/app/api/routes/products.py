from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.models import ProductVariant

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductPriceOut(BaseModel):
    id: str
    name: str
    unitPrice: int
    currency: str
    available: bool
    maxQuantity: int


class ProductPricePatch(BaseModel):
    unitPrice: int = Field(ge=0, le=100_000_000)


def product_out(product: ProductVariant) -> ProductPriceOut:
    return ProductPriceOut(
        id=product.id,
        name=product.name,
        unitPrice=product.unit_price,
        currency=product.currency,
        available=product.available,
        maxQuantity=product.max_quantity,
    )


def require_founder(user: CurrentUserDep) -> None:
    if user.role != "founder":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Founder access required")


@router.get("", response_model=list[ProductPriceOut])
async def list_products(session: SessionDep, _: CurrentUserDep):
    products = (await session.scalars(select(ProductVariant).order_by(ProductVariant.id))).all()
    return [product_out(product) for product in products]


@router.patch("/{product_id}", response_model=ProductPriceOut)
async def update_product_price(
    product_id: str,
    payload: ProductPricePatch,
    session: SessionDep,
    user: CurrentUserDep,
):
    require_founder(user)
    product = await session.get(ProductVariant, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product.unit_price = payload.unitPrice
    await session.commit()
    await session.refresh(product)
    return product_out(product)
