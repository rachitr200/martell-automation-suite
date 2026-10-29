"""Initial versioned baseline, preserving existing demo rows and tables."""
from alembic import context, op
revision='0001_operations'
down_revision=None
branch_labels=None
depends_on=None


def upgrade():
    # Initial baseline adds new tables to an existing pre-migration demo database.
    context.config.attributes['metadata'].create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; restore a reviewed database backup instead.')
