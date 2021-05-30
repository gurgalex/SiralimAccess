"""change specific realm to FK ID from String
The quest first line generated column needs to be dropped and added manually

Revision ID: 737b00dcbc93
Revises: d62f93d99624
Create Date: 2021-05-29 19:29:48.950442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.

revision = '737b00dcbc93'
down_revision = 'd62f93d99624'
branch_labels = None
depends_on = None


computed_title_first_line_obj = sa.Computed('CASE\n    WHEN instr(title, "\r\n") > 0\n    THEN substr(title, 0, instr(title, "\r\n"))\n    ELSE title END', )


def upgrade():
    from sqlalchemy.orm.session import Session
    session = Session(bind=op.get_bind())
    session.execute('PRAGMA foreign_keys = OFF;')

    with op.batch_alter_table('quest', schema=None) as batch_op:
        batch_op.drop_column('title_first_line')
        batch_op.alter_column('specific_realm', existing_type=sa.VARCHAR(), type_=sa.Integer(), existing_nullable=True)

        batch_op.add_column(sa.Column('title_first_line', sa.String(), computed_title_first_line_obj, nullable=False, index=False))


def downgrade():
    from sqlalchemy.orm.session import Session
    session = Session(bind=op.get_bind())
    session.execute('PRAGMA foreign_keys = OFF;')

    with op.batch_alter_table('quest', schema=None) as batch_op:
        batch_op.drop_column('title_first_line')
        batch_op.alter_column('specific_realm', existing_type=sa.Integer(), type_=sa.String(), existing_nullable=True)
        batch_op.add_column(sa.Column('title_first_line', sa.String(), computed_title_first_line_obj, nullable=False, index=False))
