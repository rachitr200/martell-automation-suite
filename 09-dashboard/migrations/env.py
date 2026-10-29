from alembic import context
config=context.config
engine=config.attributes.get('engine')
metadata=config.attributes.get('metadata')
if engine is None:
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from dashboard import app
    from app.models import Base
    engine=app.state.engine
    metadata=Base.metadata
config.attributes['metadata']=metadata
with engine.connect() as connection:
    context.configure(connection=connection,target_metadata=metadata)
    with context.begin_transaction():context.run_migrations()
