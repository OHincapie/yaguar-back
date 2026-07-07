from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.models import Company, User, UserCompany


class AccountsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.session.exec(select(User).where(User.email == email))  # type: ignore
        return result.first()

    async def get_user(self, user_id: str) -> User | None:
        result = await self.session.exec(select(User).where(User.id == user_id))  # type: ignore
        return result.first()

    async def get_company(self, company_id: str) -> Company | None:
        result = await self.session.exec(select(Company).where(Company.id == company_id))  # type: ignore
        return result.first()

    async def slug_exists(self, slug: str) -> bool:
        result = await self.session.exec(select(Company).where(Company.slug == slug))  # type: ignore
        return result.first() is not None

    async def create_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def create_company(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def update_company(self, company: Company) -> Company:
        self.session.add(company)
        await self.session.commit()
        await self.session.refresh(company)
        return company

    async def add_membership(self, membership: UserCompany) -> UserCompany:
        self.session.add(membership)
        await self.session.commit()
        return membership

    async def get_membership(self, user_id: str, company_id: str) -> UserCompany | None:
        result = await self.session.exec(  # type: ignore
            select(UserCompany).where(
                UserCompany.user_id == user_id, UserCompany.company_id == company_id
            )
        )
        return result.first()

    async def list_memberships(self, user_id: str) -> list[UserCompany]:
        result = await self.session.exec(select(UserCompany).where(UserCompany.user_id == user_id))  # type: ignore
        return result.all()

    async def list_company_members(self, company_id: str) -> list[tuple[UserCompany, User]]:
        result = await self.session.exec(  # type: ignore
            select(UserCompany, User)
            .where(UserCompany.company_id == company_id, UserCompany.user_id == User.id)
            .order_by(User.name)
        )
        return result.all()

    async def update_membership(self, membership: UserCompany) -> UserCompany:
        self.session.add(membership)
        await self.session.commit()
        await self.session.refresh(membership)
        return membership

    async def remove_membership(self, membership: UserCompany) -> None:
        await self.session.delete(membership)
        await self.session.commit()
