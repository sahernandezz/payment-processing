-- Initial schema for payment processing.
-- Applied by the Alembic revision 0001_initial_schema.

CREATE TABLE api_keys (
    id UUID NOT NULL,
    name VARCHAR(120) NOT NULL,
    hashed_key VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (hashed_key)
);

CREATE TABLE merchants (
    id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    document_number VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (document_number)
);

CREATE TABLE permissions (
    id UUID NOT NULL,
    code VARCHAR(80) NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (id),
    UNIQUE (code)
);

CREATE TABLE roles (
    id UUID NOT NULL,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (id),
    UNIQUE (name)
);

CREATE TABLE users (
    id UUID NOT NULL,
    email VARCHAR(255) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (email)
);

CREATE TABLE payments (
    id UUID NOT NULL,
    merchant_id UUID NOT NULL,
    external_reference VARCHAR(120) NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    payment_method VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    idempotency_key VARCHAR(120) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_merchant_external_ref UNIQUE (merchant_id, external_reference),
    FOREIGN KEY(merchant_id) REFERENCES merchants (id),
    UNIQUE (idempotency_key)
);

CREATE INDEX ix_payments_status ON payments (status);

CREATE INDEX ix_payments_merchant_id ON payments (merchant_id);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL,
    permission_id UUID NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY(role_id) REFERENCES roles (id),
    FOREIGN KEY(permission_id) REFERENCES permissions (id)
);

CREATE TABLE user_roles (
    user_id UUID NOT NULL,
    role_id UUID NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY(user_id) REFERENCES users (id),
    FOREIGN KEY(role_id) REFERENCES roles (id)
);

CREATE TABLE payment_status_history (
    id UUID NOT NULL,
    payment_id UUID NOT NULL,
    previous_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    reason VARCHAR(255),
    changed_by VARCHAR(120) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(payment_id) REFERENCES payments (id)
);

CREATE INDEX ix_payment_status_history_payment_id ON payment_status_history (payment_id);
