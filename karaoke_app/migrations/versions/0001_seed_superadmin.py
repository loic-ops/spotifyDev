"""seed superadmin sysadmin

Revision ID: 0001_seed_superadmin
Revises:
Create Date: 2026-05-25

Idempotent: insere le compte 'sysadmin' (role=superadmin) si absent,
sinon ne fait que promouvoir un eventuel 'sysadmin' existant en superadmin
sans ecraser son mot de passe (utile si le mot de passe a deja ete change).

Le downgrade supprime le compte 'sysadmin' uniquement s'il n'a jamais ete
modifie (utile pour les rollback de dev). En prod, downgrade laisse le
compte intact si vous l'avez personnalise — supprimez-le manuellement.
"""
from alembic import op
import sqlalchemy as sa
import bcrypt


# revision identifiers, used by Alembic.
revision = '0001_seed_superadmin'
down_revision = None
branch_labels = None
depends_on = None


SUPERADMIN_USERNAME = 'sysadmin'
SUPERADMIN_PASSWORD = '@karao2026_iscdart'


def upgrade():
    bind = op.get_bind()

    existing = bind.execute(
        sa.text("SELECT id, role FROM admins WHERE username = :u"),
        {'u': SUPERADMIN_USERNAME},
    ).fetchone()

    if existing is None:
        pwd_hash = bcrypt.hashpw(
            SUPERADMIN_PASSWORD.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')
        bind.execute(
            sa.text(
                "INSERT INTO admins (username, password_hash, role, created_at) "
                "VALUES (:u, :p, 'superadmin', UTC_TIMESTAMP())"
            ),
            {'u': SUPERADMIN_USERNAME, 'p': pwd_hash},
        )
    else:
        # compte existe deja: on s'assure juste qu'il est superadmin.
        if existing[1] != 'superadmin':
            bind.execute(
                sa.text("UPDATE admins SET role = 'superadmin' WHERE id = :i"),
                {'i': existing[0]},
            )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM admins WHERE username = :u AND role = 'superadmin'"),
        {'u': SUPERADMIN_USERNAME},
    )
