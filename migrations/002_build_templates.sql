-- Migração 002: Tabela de Modelos Padrão Oficiais de Construção (Cloud SQL)
-- Suporta o armazenamento e gestão dos 5 templates oficiais do sistema

CREATE TABLE IF NOT EXISTS build_templates (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    target_levels JSONB NOT NULL,
    priority_list JSONB NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_build_templates_is_default ON build_templates(is_default);
