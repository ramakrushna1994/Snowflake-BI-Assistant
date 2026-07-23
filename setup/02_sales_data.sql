-- ============================================================
-- 02_sales_data.sql
-- Sales schema: Products, Customers, Orders, Order Items
-- ============================================================

USE DATABASE CONVERSATIONAL_BI;
USE SCHEMA SALES;
USE WAREHOUSE BI_ASSISTANT_WH;

-- Products table
CREATE OR REPLACE TABLE PRODUCTS (
    PRODUCT_ID INT AUTOINCREMENT PRIMARY KEY,
    PRODUCT_NAME VARCHAR(200) NOT NULL,
    CATEGORY VARCHAR(100),
    UNIT_PRICE DECIMAL(10,2),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Customers table
CREATE OR REPLACE TABLE CUSTOMERS (
    CUSTOMER_ID INT AUTOINCREMENT PRIMARY KEY,
    FIRST_NAME VARCHAR(100),
    LAST_NAME VARCHAR(100),
    EMAIL VARCHAR(200),
    REGION VARCHAR(50),
    SEGMENT VARCHAR(50),
    CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Orders table
CREATE OR REPLACE TABLE ORDERS (
    ORDER_ID INT AUTOINCREMENT PRIMARY KEY,
    CUSTOMER_ID INT REFERENCES CUSTOMERS(CUSTOMER_ID),
    ORDER_DATE DATE NOT NULL,
    TOTAL_AMOUNT DECIMAL(12,2),
    STATUS VARCHAR(20) DEFAULT 'Completed'
);

-- Order Items table
CREATE OR REPLACE TABLE ORDER_ITEMS (
    ORDER_ITEM_ID INT AUTOINCREMENT PRIMARY KEY,
    ORDER_ID INT REFERENCES ORDERS(ORDER_ID),
    PRODUCT_ID INT REFERENCES PRODUCTS(PRODUCT_ID),
    QUANTITY INT,
    UNIT_PRICE DECIMAL(10,2)
);

-- ============================================================
-- Sample Data: Products
-- ============================================================
INSERT INTO PRODUCTS (PRODUCT_NAME, CATEGORY, UNIT_PRICE) VALUES
('Laptop Pro 15', 'Electronics', 1299.99),
('Wireless Mouse', 'Electronics', 29.99),
('USB-C Hub', 'Electronics', 49.99),
('Mechanical Keyboard', 'Electronics', 89.99),
('Monitor 27 inch', 'Electronics', 449.99),
('Webcam HD', 'Electronics', 79.99),
('Noise Cancelling Headphones', 'Electronics', 249.99),
('Tablet 10 inch', 'Electronics', 399.99),
('Smartwatch', 'Electronics', 199.99),
('Portable Charger', 'Electronics', 39.99),
('Office Chair Ergonomic', 'Furniture', 599.99),
('Standing Desk', 'Furniture', 799.99),
('Bookshelf Oak', 'Furniture', 249.99),
('Filing Cabinet', 'Furniture', 179.99),
('Desk Lamp LED', 'Furniture', 59.99),
('Notebook A4 Pack', 'Stationery', 12.99),
('Pen Set Premium', 'Stationery', 24.99),
('Whiteboard 4x3', 'Stationery', 89.99),
('Sticky Notes Bundle', 'Stationery', 8.99),
('Planner 2025', 'Stationery', 19.99),
('Coffee Maker', 'Appliances', 129.99),
('Water Purifier', 'Appliances', 299.99),
('Air Purifier', 'Appliances', 199.99),
('Desk Fan', 'Appliances', 34.99),
('Mini Fridge', 'Appliances', 179.99);

-- ============================================================
-- Sample Data: Customers
-- ============================================================
INSERT INTO CUSTOMERS (FIRST_NAME, LAST_NAME, EMAIL, REGION, SEGMENT) VALUES
('Alice', 'Johnson', 'alice.johnson@email.com', 'North', 'Enterprise'),
('Bob', 'Smith', 'bob.smith@email.com', 'South', 'SMB'),
('Carol', 'Williams', 'carol.williams@email.com', 'East', 'Enterprise'),
('David', 'Brown', 'david.brown@email.com', 'West', 'Mid-Market'),
('Eva', 'Davis', 'eva.davis@email.com', 'North', 'SMB'),
('Frank', 'Miller', 'frank.miller@email.com', 'South', 'Enterprise'),
('Grace', 'Wilson', 'grace.wilson@email.com', 'East', 'Mid-Market'),
('Henry', 'Moore', 'henry.moore@email.com', 'West', 'SMB'),
('Iris', 'Taylor', 'iris.taylor@email.com', 'North', 'Enterprise'),
('Jack', 'Anderson', 'jack.anderson@email.com', 'South', 'Mid-Market'),
('Karen', 'Thomas', 'karen.thomas@email.com', 'East', 'SMB'),
('Leo', 'Jackson', 'leo.jackson@email.com', 'West', 'Enterprise'),
('Mia', 'White', 'mia.white@email.com', 'North', 'Mid-Market'),
('Nathan', 'Harris', 'nathan.harris@email.com', 'South', 'SMB'),
('Olivia', 'Martin', 'olivia.martin@email.com', 'East', 'Enterprise'),
('Paul', 'Garcia', 'paul.garcia@email.com', 'West', 'Mid-Market'),
('Quinn', 'Martinez', 'quinn.martinez@email.com', 'North', 'SMB'),
('Rachel', 'Robinson', 'rachel.robinson@email.com', 'South', 'Enterprise'),
('Steve', 'Clark', 'steve.clark@email.com', 'East', 'Mid-Market'),
('Tina', 'Lewis', 'tina.lewis@email.com', 'West', 'SMB');

-- ============================================================
-- Sample Data: Orders (spread across last 6 months)
-- ============================================================
INSERT INTO ORDERS (CUSTOMER_ID, ORDER_DATE, TOTAL_AMOUNT, STATUS) VALUES
(1, '2025-01-05', 1349.98, 'Completed'),
(2, '2025-01-12', 79.98, 'Completed'),
(3, '2025-01-18', 899.98, 'Completed'),
(4, '2025-01-25', 249.99, 'Completed'),
(5, '2025-02-02', 129.98, 'Completed'),
(6, '2025-02-10', 1599.98, 'Completed'),
(7, '2025-02-15', 449.99, 'Completed'),
(8, '2025-02-22', 59.98, 'Completed'),
(9, '2025-03-01', 2099.97, 'Completed'),
(10, '2025-03-08', 339.98, 'Completed'),
(11, '2025-03-15', 89.99, 'Completed'),
(12, '2025-03-22', 799.99, 'Completed'),
(13, '2025-03-28', 179.98, 'Completed'),
(14, '2025-04-05', 499.98, 'Completed'),
(15, '2025-04-12', 1299.99, 'Completed'),
(16, '2025-04-18', 649.98, 'Completed'),
(17, '2025-04-25', 39.99, 'Completed'),
(18, '2025-05-02', 929.98, 'Completed'),
(19, '2025-05-10', 279.98, 'Completed'),
(20, '2025-05-15', 199.99, 'Completed'),
(1, '2025-05-20', 449.99, 'Completed'),
(3, '2025-05-28', 349.98, 'Completed'),
(5, '2025-06-01', 1299.99, 'Completed'),
(7, '2025-06-05', 599.99, 'Completed'),
(9, '2025-06-10', 249.99, 'Completed'),
(2, '2025-06-15', 89.99, 'Completed'),
(4, '2025-06-18', 179.99, 'Completed'),
(6, '2025-06-20', 799.99, 'Completed'),
(8, '2025-06-22', 129.99, 'Completed'),
(10, '2025-06-25', 449.99, 'Completed'),
(11, '2025-06-28', 1299.99, 'Shipped'),
(12, '2025-06-29', 249.99, 'Shipped'),
(13, '2025-06-30', 599.99, 'Processing'),
(14, '2025-06-30', 89.99, 'Processing'),
(15, '2025-06-30', 1799.98, 'Processing');

-- ============================================================
-- Sample Data: Order Items
-- ============================================================
INSERT INTO ORDER_ITEMS (ORDER_ID, PRODUCT_ID, QUANTITY, UNIT_PRICE) VALUES
(1, 1, 1, 1299.99), (1, 2, 1, 29.99), (1, 3, 1, 49.99),
(2, 2, 1, 29.99), (2, 3, 1, 49.99),
(3, 5, 2, 449.99),
(4, 8, 1, 249.99), (4, 10, 1, 39.99),
(5, 2, 2, 29.99), (5, 4, 1, 89.99),
(6, 1, 1, 1299.99), (6, 6, 1, 79.99), (6, 7, 1, 249.99),
(7, 5, 1, 449.99),
(8, 16, 2, 12.99), (8, 17, 1, 24.99),
(9, 1, 1, 1299.99), (9, 11, 1, 599.99), (9, 9, 1, 199.99),
(10, 7, 1, 249.99), (10, 4, 1, 89.99),
(11, 4, 1, 89.99),
(12, 12, 1, 799.99),
(13, 15, 2, 59.99), (13, 19, 2, 8.99),
(14, 8, 1, 399.99), (14, 9, 1, 199.99),
(15, 1, 1, 1299.99),
(16, 11, 1, 599.99), (16, 3, 1, 49.99),
(17, 10, 1, 39.99),
(18, 5, 1, 449.99), (18, 7, 1, 249.99), (18, 6, 1, 79.99),
(19, 13, 1, 249.99), (19, 2, 1, 29.99),
(20, 9, 1, 199.99),
(21, 5, 1, 449.99),
(22, 13, 1, 249.99), (22, 10, 2, 39.99),
(23, 1, 1, 1299.99),
(24, 11, 1, 599.99),
(25, 8, 1, 249.99), (25, 10, 1, 39.99),
(26, 4, 1, 89.99),
(27, 14, 1, 179.99),
(28, 12, 1, 799.99),
(29, 21, 1, 129.99),
(30, 5, 1, 449.99),
(31, 1, 1, 1299.99),
(32, 7, 1, 249.99),
(33, 11, 1, 599.99),
(34, 4, 1, 89.99),
(35, 1, 1, 1299.99), (35, 5, 1, 449.99);
