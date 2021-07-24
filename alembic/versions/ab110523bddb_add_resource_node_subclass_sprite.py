"""add resource_node subclass sprite

Revision ID: ab110523bddb
Revises: c7cd192c6c56
Create Date: 2021-07-23 14:01:18.484356

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy import orm

import subot.models as models

revision = 'ab110523bddb'
down_revision = 'c7cd192c6c56'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    bind = op.get_bind()
    session = orm.Session(bind=bind)

    op.create_table('resource_node_sprite',
                    sa.Column('sprite_id', sa.Integer(), nullable=False, primary_key=True),
                    sa.Column('realm_id', sa.Integer(), nullable=False, primary_key=True),
                    sa.ForeignKeyConstraint(['realm_id'], ['realm.id'], ),
                    sa.ForeignKeyConstraint(['sprite_id'], ['sprite.id'], )
    )

    r_type = models.SpriteTypeLookup()
    r_type.id = models.SpriteType.RESOURCE_NODE.value
    r_type.name = models.SpriteType.RESOURCE_NODE.name

    session.add(r_type)
    session.commit()

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###

    op.drop_table('resource_node_sprite')
    op.execute("DELETE FROM sprite_type WHERE id=11;")
