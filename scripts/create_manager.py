import asyncio
import getpass
import sys

from app.db.session import AsyncSessionLocal, engine
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services import user_service


async def main(name: str, email: str) -> None:
    password = getpass.getpass("Senha (mín. 10 caracteres): ")
    if password != getpass.getpass("Repita a senha: "):
        sys.exit("As senhas não conferem.")

    data = UserCreate(name=name, email=email, password=password, role=UserRole.MANAGER)
    try:
        async with AsyncSessionLocal() as db:
            user = await user_service.create_user(db, data, actor=None, ip=None)
    except user_service.EmailAlreadyExistsError:
        sys.exit("Esse e-mail já está cadastrado.")
    finally:
        await engine.dispose()
    print(f"Gerente criado: {user.email} ({user.id})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Uso: python -m scripts.create_manager 'Nome' email@exemplo.com")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
