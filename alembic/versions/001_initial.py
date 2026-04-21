# Migration script for payments and outbox_messages tables

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type for payment status
    payment_status = sa.Enum('pending', 'succeeded', 'failed', name='paymentstatus')
    payment_status.create(op.get_bind())

    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.String(64), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('status', payment_status, nullable=False, default='pending'),
        sa.Column('idempotency_key', sa.String(128), nullable=False),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for payments table
    op.create_index('ix_payments_idempotency_key', 'payments', ['idempotency_key'])
    op.create_index('ix_payments_status_created', 'payments', ['status', 'created_at'])

    # Create outbox_messages table
    op.create_table(
        'outbox_messages',
        sa.Column('id', sa.Integer, autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('published', sa.Boolean, nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create index for outbox_messages table
    op.create_index('ix_outbox_published_created', 'outbox_messages', ['published', 'created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_outbox_published_created', table_name='outbox_messages')
    op.drop_index('ix_payments_status_created', table_name='payments')
    op.drop_index('ix_payments_idempotency_key', table_name='payments')

    # Drop tables
    op.drop_table('outbox_messages')
    op.drop_table('payments')

    # Drop enum type
    sa.Enum(name='paymentstatus').drop(op.get_bind())
