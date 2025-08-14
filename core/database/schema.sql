-- Astra Annotator Database Schema

-- Conditions (mental health conditions)
CREATE TABLE IF NOT EXISTS conditions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prompt groups (flexible: 3x3 grid, single prompt, or list)
CREATE TABLE IF NOT EXISTS prompt_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id INTEGER NOT NULL,
    name TEXT NOT NULL, -- e.g., "Moderate Severity Focus"
    description TEXT,
    group_type TEXT DEFAULT 'grid_3x3' CHECK (group_type IN ('grid_3x3', 'single', 'list')),
    risk_category TEXT,
    low_severity_explanation TEXT,
    moderate_severity_explanation TEXT,
    high_severity_explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (condition_id) REFERENCES conditions(id),
    UNIQUE(condition_id, name)
);

-- Individual prompts (flexible based on group type)
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    communication_style TEXT CHECK (communication_style IN ('implicit', 'neutral', 'explicit')),
    severity TEXT CHECK (severity IN ('low', 'moderate', 'high')),
    list_order INTEGER, -- For list-type groups, defines order within the list
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES prompt_groups(id)
);

-- Additional labels for prompts (key-value pairs)
CREATE TABLE IF NOT EXISTS prompt_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    label_key TEXT NOT NULL,
    label_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id),
    UNIQUE(prompt_id, label_key)
);

-- Experiments
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    models TEXT NOT NULL, -- JSON array of model names
    status TEXT DEFAULT 'created' CHECK (status IN ('created', 'running', 'completed', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Experiment-prompt associations
CREATE TABLE IF NOT EXISTS experiment_prompts (
    experiment_id INTEGER,
    prompt_id INTEGER,
    PRIMARY KEY (experiment_id, prompt_id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- LLM responses
CREATE TABLE IF NOT EXISTS llm_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    prompt_id INTEGER NOT NULL,
    model TEXT NOT NULL,
    response_text TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id)
);

-- Annotation runs
CREATE TABLE IF NOT EXISTS annotation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    guidelines TEXT,
    response_ordering TEXT CHECK (response_ordering IN ('sequential', 'randomized')),
    filter_models TEXT, -- JSON array of models to include
    filter_conditions TEXT, -- JSON array of conditions to include
    status TEXT DEFAULT 'setup' CHECK (status IN ('setup', 'active', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

-- Assessment categories
CREATE TABLE IF NOT EXISTS assessment_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annotation_run_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    type TEXT CHECK (type IN ('categorical', 'binary', 'text')),
    possible_values TEXT, -- JSON array for categorical/binary types
    guidelines TEXT,
    display_order INTEGER,
    FOREIGN KEY (annotation_run_id) REFERENCES annotation_runs(id)
);

-- Labeler assignments
CREATE TABLE IF NOT EXISTS labeler_assignments (
    annotation_run_id INTEGER,
    labeler_initials TEXT,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (annotation_run_id, labeler_initials),
    FOREIGN KEY (annotation_run_id) REFERENCES annotation_runs(id)
);

-- Annotations
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annotation_run_id INTEGER NOT NULL,
    response_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    labeler_initials TEXT NOT NULL,
    value TEXT NOT NULL,
    justification TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (annotation_run_id) REFERENCES annotation_runs(id),
    FOREIGN KEY (response_id) REFERENCES llm_responses(id),
    FOREIGN KEY (category_id) REFERENCES assessment_categories(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_prompt_groups_condition_id ON prompt_groups(condition_id);
CREATE INDEX IF NOT EXISTS idx_prompt_groups_type ON prompt_groups(group_type);
CREATE INDEX IF NOT EXISTS idx_prompts_group_id ON prompts(group_id);
CREATE INDEX IF NOT EXISTS idx_prompts_communication_style ON prompts(communication_style);
CREATE INDEX IF NOT EXISTS idx_prompts_severity ON prompts(severity);
CREATE INDEX IF NOT EXISTS idx_prompts_list_order ON prompts(group_id, list_order);
CREATE INDEX IF NOT EXISTS idx_prompt_labels_prompt_id ON prompt_labels(prompt_id);
CREATE INDEX IF NOT EXISTS idx_prompt_labels_key ON prompt_labels(label_key);
CREATE INDEX IF NOT EXISTS idx_llm_responses_experiment_prompt ON llm_responses(experiment_id, prompt_id);
CREATE INDEX IF NOT EXISTS idx_llm_responses_status ON llm_responses(status);
CREATE INDEX IF NOT EXISTS idx_annotations_run_labeler ON annotations(annotation_run_id, labeler_initials);
CREATE INDEX IF NOT EXISTS idx_annotations_response_category ON annotations(response_id, category_id);
