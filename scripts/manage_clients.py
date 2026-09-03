"""
Tribal Wars Bot - Commercial Client & License Management CLI
Ferramenta administrativa de linha de comandos para gerir clientes, subscrições e licenças no Cloud SQL.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import sys
from pathlib import Path

# Garante que a raiz do projeto está no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.storage.cloud_db import get_cloud_db


try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

async def cmd_list(args):
    db = get_cloud_db()
    await db.init_db()
    users = await db.user_repo.list_all_users()

    print("\n" + "=" * 95)
    print(f"{'EMAIL':<30} | {'LICENCA':<10} | {'ESTADO':<10} | {'VALIDADE':<18} | {'CONTAS':<7} | {'NOTAS'}")
    print("-" * 95)

    now = datetime.now(timezone.utc)
    for u in users:
        is_active = getattr(u, "is_active", True)
        status_str = "[ATIVO]" if is_active else "[SUSPENSO]"

        if u.expires_at is None:
            validade_str = "Vitalicio"
        elif u.expires_at < now:
            diff = (now - u.expires_at).days
            validade_str = f"Expirou ({diff}d)"
            status_str = "[EXPIRADO]"
        else:
            diff = (u.expires_at - now).days
            validade_str = f"{diff}d restantes"

        accounts = await db.account_repo.list_by_user(u.id)
        max_acc = getattr(u, "max_accounts", 1)
        contas_str = f"{len(accounts)}/{max_acc}"
        notes_str = (u.notes or "-")[:20]

        print(f"{u.email:<30} | {u.license_type:<10} | {status_str:<10} | {validade_str:<18} | {contas_str:<7} | {notes_str}")

    print("=" * 95)
    print(f"Total de Clientes: {len(users)}\n")


async def cmd_create(args):
    db = get_cloud_db()
    existing = await db.user_repo.get_by_email(args.email)
    if existing:
        print(f"\n[ERRO] Já existe um cliente registado com o email '{args.email}'.")
        sys.exit(1)

    user = await db.user_repo.create_user(
        email=args.email,
        password=args.password,
        license_type=args.license,
        days_valid=args.days,
        max_accounts=args.max_accounts,
        notes=args.notes,
    )

    now = datetime.now(timezone.utc)
    val_str = f"{args.days} dias (até {user.expires_at.strftime('%d/%m/%Y %H:%M')})" if user.expires_at else "Vitalício"

    print("\n" + "=" * 65)
    print(" [CLIENTE CRIADO COM SUCESSO]")
    print("=" * 65)
    print(f" ID:            {user.id}")
    print(f" Email:         {user.email}")
    print(f" Tipo Licença:  {user.license_type}")
    print(f" Validade:      {val_str}")
    print(f" Limite Contas: {user.max_accounts}")
    if user.notes:
        print(f" Notas:         {user.notes}")
    print("=" * 65 + "\n")


async def cmd_extend(args):
    db = get_cloud_db()
    user = await db.user_repo.extend_subscription(args.email, days=args.days)
    if not user:
        print(f"\n[ERRO] Cliente '{args.email}' não encontrado.")
        sys.exit(1)

    exp_str = user.expires_at.strftime("%d/%m/%Y %H:%M") if user.expires_at else "Vitalício"
    print(f"\n[SUCESSO] Subscrição de '{user.email}' estendida por +{args.days} dias.")
    print(f" Nova data de expiração: {exp_str}\n")


async def cmd_toggle(args):
    db = get_cloud_db()
    user = await db.user_repo.get_by_email(args.email)
    if not user:
        print(f"\n[ERRO] Cliente '{args.email}' não encontrado.")
        sys.exit(1)

    new_status = not getattr(user, "is_active", True)
    updated = await db.user_repo.set_active_status(args.email, new_status)
    status_label = "ATIVADA" if new_status else "SUSPENSA"
    print(f"\n[SUCESSO] A conta de '{updated.email}' foi {status_label}.\n")


async def cmd_password(args):
    db = get_cloud_db()
    updated = await db.user_repo.update_password(args.email, args.new_password)
    if not updated:
        print(f"\n[ERRO] Cliente '{args.email}' não encontrado.")
        sys.exit(1)
    print(f"\n[SUCESSO] Palavra-passe de '{updated.email}' atualizada com sucesso.\n")


async def cmd_delete(args):
    db = get_cloud_db()
    user = await db.user_repo.get_by_email(args.email)
    if not user:
        print(f"\n[ERRO] Cliente '{args.email}' não encontrado.")
        sys.exit(1)

    if not args.yes:
        confirm = input(f"Tem a certeza de que deseja eliminar o cliente '{user.email}' e todas as suas contas associadas? (s/N): ")
        if confirm.lower() not in ("s", "sim", "y", "yes"):
            print("Operação cancelada.")
            return

    success = await db.user_repo.delete_user(args.email)
    if success:
        print(f"\n[SUCESSO] Cliente '{args.email}' eliminado da base de dados.\n")
    else:
        print(f"\n[ERRO] Falha ao eliminar cliente '{args.email}'.\n")


async def cmd_info(args):
    db = get_cloud_db()
    await db.init_db()
    user = await db.user_repo.get_by_email(args.email)
    if not user:
        print(f"\n[ERRO] Cliente '{args.email}' não encontrado.")
        sys.exit(1)

    accounts = await db.account_repo.list_by_user(user.id)
    now = datetime.now(timezone.utc)
    is_active = getattr(user, "is_active", True)

    print("\n" + "=" * 65)
    print(f" FICHA DE CLIENTE: {user.email}")
    print("=" * 65)
    print(f" ID Utilizador:    {user.id}")
    print(f" Tipo Licenca:     {user.license_type}")
    print(f" Estado:           {'[ATIVA]' if is_active else '[SUSPENSA]'}")
    if user.expires_at:
        days_diff = (user.expires_at - now).days
        status_exp = f"{days_diff} dias restantes" if days_diff >= 0 else f"Expirou ha {abs(days_diff)} dias"
        print(f" Data Expiracao:   {user.expires_at.strftime('%d/%m/%Y %H:%M UTC')} ({status_exp})")
    else:
        print(" Data Expiracao:   Vitalicio (Sem expiracao)")
    print(f" Limite Contas:    {len(accounts)} / {getattr(user, 'max_accounts', 1)}")
    print(f" Registado em:     {user.created_at.strftime('%d/%m/%Y %H:%M') if user.created_at else '-'}")
    if user.notes:
        print(f" Notas Comerciais: {user.notes}")

    print("\n [Contas Tribal Wars Associadas]")
    if accounts:
        for a in accounts:
            worlds = await db.world_repo.list_by_account(a.id)
            w_str = ", ".join([w.world_code.upper() for w in worlds]) if worlds else "Nenhum"
            villages = await db.village_repo.list_by_account(a.id)
            print(f"  - Jogador: {a.game_username:<16} | Mundos: {w_str:<12} | Aldeias: {len(villages)}")
    else:
        print("  (Nenhuma conta Tribal Wars associada ainda)")
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Tribal Wars Bot - Gestão de Clientes e Subscrições Comerciais (Cloud SQL)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="Lista todos os clientes e estado das licenças")
    p_list.set_defaults(func=cmd_list)

    # create
    p_create = subparsers.add_parser("create", help="Cria um novo cliente com subscrição")
    p_create.add_argument("email", help="Email do cliente")
    p_create.add_argument("password", help="Palavra-passe de acesso à aplicação")
    p_create.add_argument("--days", type=int, default=30, help="Dias de validade da subscrição (padrão: 30)")
    p_create.add_argument("--license", default="standard", choices=["standard", "pro", "vip"], help="Tipo de licença")
    p_create.add_argument("--max-accounts", type=int, default=1, help="Número máximo de contas TW (padrão: 1)")
    p_create.add_argument("--notes", default="", help="Notas (ex: contacto WhatsApp, ref. de pagamento)")
    p_create.set_defaults(func=cmd_create)

    # extend
    p_ext = subparsers.add_parser("extend", help="Renova ou estende a validade da subscrição por X dias")
    p_ext.add_argument("email", help="Email do cliente")
    p_ext.add_argument("--days", type=int, default=30, help="Dias a adicionar (padrão: 30)")
    p_ext.set_defaults(func=cmd_extend)

    # toggle
    p_tog = subparsers.add_parser("toggle", help="Suspende ou reativa a conta do cliente")
    p_tog.add_argument("email", help="Email do cliente")
    p_tog.set_defaults(func=cmd_toggle)

    # password
    p_pwd = subparsers.add_parser("password", help="Altera a palavra-passe do cliente")
    p_pwd.add_argument("email", help="Email do cliente")
    p_pwd.add_argument("new_password", help="Nova palavra-passe")
    p_pwd.set_defaults(func=cmd_password)

    # delete
    p_del = subparsers.add_parser("delete", help="Elimina um cliente e todas as suas contas")
    p_del.add_argument("email", help="Email do cliente")
    p_del.add_argument("-y", "--yes", action="store_true", help="Ignora pedido de confirmação")
    p_del.set_defaults(func=cmd_delete)

    # info
    p_inf = subparsers.add_parser("info", help="Mostra os detalhes completos e contas do cliente")
    p_inf.add_argument("email", help="Email do cliente")
    p_inf.set_defaults(func=cmd_info)

    args = parser.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
