-- MySQL schema for the Online Retail time-series pipeline.
-- One row in invoice_lines is one product line of an invoice, the same
-- granularity as the cleaned dataset from Task 1.
-- Run with: mysql -u retail -p retail < database/sql/schema.sql

DROP VIEW IF EXISTS daily_revenue;
DROP TABLE IF EXISTS invoice_lines;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS countries;

CREATE TABLE countries (
    country_id INT NOT NULL AUTO_INCREMENT,
    name       VARCHAR(60) NOT NULL,
    PRIMARY KEY (country_id),
    UNIQUE (name)
);

-- Missing customer IDs are stored as 'UNKNOWN' so the foreign key stays valid.
-- Codes use a binary collation because they are case-sensitive (15056BL and 15056bl differ).
CREATE TABLE customers (
    customer_id VARCHAR(20) COLLATE utf8mb4_bin NOT NULL,
    PRIMARY KEY (customer_id)
);

CREATE TABLE products (
    stock_code  VARCHAR(20) COLLATE utf8mb4_bin NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (stock_code)
);

CREATE TABLE invoices (
    invoice_no   VARCHAR(20) COLLATE utf8mb4_bin NOT NULL,
    invoice_date DATETIME NOT NULL,
    customer_id  VARCHAR(20) COLLATE utf8mb4_bin NOT NULL,
    country_id   INT NOT NULL,
    is_cancelled BOOL NOT NULL,
    PRIMARY KEY (invoice_no),
    FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
    FOREIGN KEY (country_id) REFERENCES countries (country_id)
);

-- The date index supports the latest-record and date-range queries
CREATE INDEX ix_invoices_invoice_date ON invoices (invoice_date);
CREATE INDEX ix_invoices_customer_id ON invoices (customer_id);

CREATE TABLE invoice_lines (
    line_id    INT NOT NULL AUTO_INCREMENT,
    invoice_no VARCHAR(20) COLLATE utf8mb4_bin NOT NULL,
    stock_code VARCHAR(20) COLLATE utf8mb4_bin NOT NULL,
    quantity   INT NOT NULL,
    unit_price DECIMAL(10, 3) NOT NULL,
    PRIMARY KEY (line_id),
    FOREIGN KEY (invoice_no) REFERENCES invoices (invoice_no),
    FOREIGN KEY (stock_code) REFERENCES products (stock_code)
);

CREATE INDEX ix_invoice_lines_invoice_no ON invoice_lines (invoice_no);
CREATE INDEX ix_invoice_lines_stock_code ON invoice_lines (stock_code);

-- Daily series used for forecasting (same definitions as aggregate_daily in Task 1)
CREATE VIEW daily_revenue AS
SELECT DATE(i.invoice_date)                                                       AS sale_date,
       SUM(CASE WHEN NOT i.is_cancelled THEN l.quantity * l.unit_price ELSE 0 END) AS gross_revenue,
       SUM(l.quantity * l.unit_price)                                             AS net_revenue,
       COUNT(DISTINCT CASE WHEN NOT i.is_cancelled THEN i.invoice_no END)          AS n_invoices,
       SUM(CASE WHEN NOT i.is_cancelled THEN l.quantity ELSE 0 END)               AS total_quantity
FROM invoice_lines l
JOIN invoices i ON i.invoice_no = l.invoice_no
GROUP BY DATE(i.invoice_date);
