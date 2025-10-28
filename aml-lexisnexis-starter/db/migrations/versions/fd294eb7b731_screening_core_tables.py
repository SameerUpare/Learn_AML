from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_screening_core"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Vector storage
    op.execute("""
    CREATE TABLE IF NOT EXISTS sanction_vectors (
      entity_id TEXT PRIMARY KEY,
      model_name TEXT NOT NULL,
      dim INTEGER NOT NULL,
      vec BLOB NOT NULL,
      updated_at TEXT NOT NULL
    );
    """)

    # Analyst labels
    op.execute("""
    CREATE TABLE IF NOT EXISTS analyst_labels (
      query_id TEXT NOT NULL,
      candidate_entity_id TEXT NOT NULL,
      relevance INTEGER NOT NULL,
      labeled_by TEXT,
      labeled_at TEXT NOT NULL,
      PRIMARY KEY (query_id, candidate_entity_id)
    );
    """)

    # Monitoring snapshots
    op.execute("""
    CREATE TABLE IF NOT EXISTS screening_metrics (
      ts TEXT NOT NULL,
      window TEXT NOT NULL,
      total INT, retrieved INT, reviewed INT,
      tp INT, fp INT, fn INT,
      p95_latency_ms REAL,
      drift_name REAL, drift_country REAL, drift_embed REAL,
      PRIMARY KEY (ts, window)
    );
    """)

    # Lightweight config
    op.execute("""
    CREATE TABLE IF NOT EXISTS screening_config (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );
    """)

    # Seed defaults
    op.execute("""
    INSERT OR REPLACE INTO screening_config(key,value) VALUES
     ('weight.name.sim','0.60'),
     ('weight.context','0.25'),
     ('weight.embed','0.15'),
     ('embed.model','paraphrase-multilingual-MiniLM-L12-v2'),
     ('faiss.threshold','200000');
    """)

def downgrade():
    # Drop only what we created
    op.execute("DROP TABLE IF EXISTS screening_config;")
    op.execute("DROP TABLE IF EXISTS screening_metrics;")
    op.execute("DROP TABLE IF EXISTS analyst_labels;")
    op.execute("DROP TABLE IF EXISTS sanction_vectors;")
