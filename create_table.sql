CREATE TABLE data_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    runtime_version TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    instruction TEXT NOT NULL,
    iteration_number INTEGER NOT NULL,
    in_iteration_number INTEGER NOT NULL,

    input_game_state_json TEXT NOT NULL,
    execution_history_json TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    agent_output_json TEXT NOT NULL,
    evaluation_json TEXT NOT NULL,
    evaluated_game_state_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_unique_data_points
ON data_points (
    collection_id,
    step_number
);

CREATE TABLE programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    value REAL DEFAULT 0.0,
    visits INTEGER DEFAULT 0,
    parent_id INTEGER,
    state_json TEXT,
    conversation_json TEXT NOT NULL,
    completion_token_usage INTEGER,
    prompt_token_usage INTEGER,
    token_usage INTEGER,
    response TEXT,
    holdout_value REAL,
    raw_reward REAL,
    version INTEGER DEFAULT 1,
    version_description TEXT DEFAULT '',
    model TEXT DEFAULT 'gpt-4o',
    meta TEXT,
    achievements_json TEXT,
    instance INTEGER DEFAULT -1,
    depth REAL DEFAULT 0.0,
    advantage REAL DEFAULT 0.0,
    ticks INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);