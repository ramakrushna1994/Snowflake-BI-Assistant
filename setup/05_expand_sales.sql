-- ============================================================
-- 05_expand_sales.sql
-- Expand SALES schema: more tables, finer grain, high volume
-- ============================================================

USE DATABASE CONVERSATIONAL_BI;
USE SCHEMA SALES;
USE WAREHOUSE BI_ASSISTANT_WH;

-- ── SALES_CHANNELS ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS SALES_CHANNELS (
    CHANNEL_ID   INT AUTOINCREMENT PRIMARY KEY,
    CHANNEL_NAME VARCHAR(50),
    CHANNEL_TYPE VARCHAR(30)   -- Online, Retail, Wholesale, Partner
);

INSERT INTO SALES_CHANNELS (CHANNEL_NAME, CHANNEL_TYPE)
SELECT c.*
FROM (SELECT 'Website' AS CHANNEL_NAME, 'Online' AS CHANNEL_TYPE UNION ALL
      SELECT 'Mobile App','Online' UNION ALL SELECT 'In-Store','Retail' UNION ALL
      SELECT 'Distributor','Wholesale' UNION ALL SELECT 'Partner Portal','Partner') c
WHERE NOT EXISTS (SELECT 1 FROM SALES_CHANNELS LIMIT 1);

-- ── STORES ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS STORES (
    STORE_ID    INT AUTOINCREMENT PRIMARY KEY,
    STORE_NAME  VARCHAR(100),
    CITY        VARCHAR(80),
    STATE       VARCHAR(30),
    REGION      VARCHAR(20),
    OPENED_DATE DATE
);

INSERT INTO STORES (STORE_NAME, CITY, STATE, REGION, OPENED_DATE) VALUES
('NYC Flagship','New York','NY','East','2018-03-01'),
('Brooklyn Hub','Brooklyn','NY','East','2019-07-15'),
('Boston Outlet','Boston','MA','East','2020-01-10'),
('Chicago Main','Chicago','IL','Central','2018-06-01'),
('Houston Store','Houston','TX','South','2019-03-20'),
('Dallas Outlet','Dallas','TX','South','2021-05-01'),
('Atlanta Hub','Atlanta','GA','South','2020-09-15'),
('Miami Store','Miami','FL','South','2022-02-01'),
('LA Flagship','Los Angeles','CA','West','2017-11-01'),
('San Francisco','San Francisco','CA','West','2019-01-20'),
('Seattle Hub','Seattle','WA','West','2020-04-01'),
('Denver Outlet','Denver','CO','West','2021-08-15'),
('Phoenix Store','Phoenix','AZ','West','2022-01-10'),
('Minneapolis Hub','Minneapolis','MN','Central','2021-03-01'),
('Kansas City','Kansas City','MO','Central','2022-06-01'),
('Charlotte','Charlotte','NC','East','2021-11-01'),
('Nashville','Nashville','TN','South','2022-03-15'),
('Portland','Portland','OR','West','2023-01-01'),
('Detroit','Detroit','MI','Central','2022-09-01'),
('Columbus','Columbus','OH','Central','2023-04-01');

-- ── PROMOTIONS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS PROMOTIONS (
    PROMO_ID        INT AUTOINCREMENT PRIMARY KEY,
    PROMO_CODE      VARCHAR(20),
    PROMO_NAME      VARCHAR(100),
    DISCOUNT_TYPE   VARCHAR(20),   -- PERCENT, FIXED
    DISCOUNT_VALUE  DECIMAL(8,2),
    MIN_ORDER_VALUE DECIMAL(10,2),
    START_DATE      DATE,
    END_DATE        DATE,
    CHANNEL_ID      INT
);

INSERT INTO PROMOTIONS (PROMO_CODE,PROMO_NAME,DISCOUNT_TYPE,DISCOUNT_VALUE,MIN_ORDER_VALUE,START_DATE,END_DATE,CHANNEL_ID) VALUES
('SAVE10','10% Off Sitewide','PERCENT',10,50,'2024-01-01','2024-01-31',1),
('SAVE15','15% Off Electronics','PERCENT',15,200,'2024-02-01','2024-02-28',1),
('FLASH20','Flash Sale 20%','PERCENT',20,100,'2024-03-15','2024-03-17',2),
('SPRING25','Spring Sale','PERCENT',25,150,'2024-04-01','2024-04-30',1),
('FIXED50','$50 Off Orders >$500','FIXED',50,500,'2024-05-01','2024-05-31',1),
('SUMMER10','Summer Discount','PERCENT',10,75,'2024-06-01','2024-08-31',3),
('BACK2SCH','Back to School','PERCENT',12,100,'2024-08-01','2024-09-15',2),
('FALL15','Fall Collection','PERCENT',15,200,'2024-09-01','2024-10-31',1),
('BFCM30','Black Friday 30% Off','PERCENT',30,200,'2024-11-29','2024-11-30',1),
('CYBER25','Cyber Monday','PERCENT',25,150,'2024-12-02','2024-12-02',2),
('HOLIDAY20','Holiday Season','PERCENT',20,100,'2024-12-10','2024-12-25',1),
('NEWYEAR','New Year Sale','PERCENT',15,100,'2025-01-01','2025-01-07',1),
('VIP30','VIP Customer 30% Off','PERCENT',30,300,'2024-01-01','2025-12-31',5),
('WHOLESALE10','Wholesale Discount','PERCENT',10,1000,'2024-01-01','2025-12-31',4),
('APP15','App-Only 15% Off','PERCENT',15,50,'2024-01-01','2025-12-31',2);

-- ── PRODUCTS (expand schema and reload with 100 rows) ─────────────────────
CREATE TABLE IF NOT EXISTS PRODUCTS (
    PRODUCT_ID     INT AUTOINCREMENT PRIMARY KEY,
    PRODUCT_NAME   VARCHAR(200),
    CATEGORY       VARCHAR(100),
    SUBCATEGORY    VARCHAR(100),
    UNIT_COST      DECIMAL(10,2),
    UNIT_PRICE     DECIMAL(10,2),
    SUPPLIER       VARCHAR(100),
    IS_ACTIVE      BOOLEAN DEFAULT TRUE,
    LAUNCH_DATE    DATE,
    CREATED_AT     TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Add columns that may not exist from 02_sales_data.sql
ALTER TABLE PRODUCTS ADD COLUMN IF NOT EXISTS SUBCATEGORY VARCHAR(100);
ALTER TABLE PRODUCTS ADD COLUMN IF NOT EXISTS UNIT_COST DECIMAL(10,2);
ALTER TABLE PRODUCTS ADD COLUMN IF NOT EXISTS SUPPLIER VARCHAR(100);
ALTER TABLE PRODUCTS ADD COLUMN IF NOT EXISTS IS_ACTIVE BOOLEAN;
ALTER TABLE PRODUCTS ADD COLUMN IF NOT EXISTS LAUNCH_DATE DATE;

-- Reload product data only if table has fewer than 90 rows (i.e. still from 02)
TRUNCATE TABLE PRODUCTS;

INSERT INTO PRODUCTS (PRODUCT_NAME,CATEGORY,SUBCATEGORY,UNIT_COST,UNIT_PRICE,SUPPLIER,LAUNCH_DATE) VALUES
('Laptop Pro 15','Electronics','Computers',700,1299.99,'TechCorp','2022-01-01'),
('Laptop Air 13','Electronics','Computers',500,999.99,'TechCorp','2022-06-01'),
('Laptop Budget 11','Electronics','Computers',250,499.99,'BudgetTech','2023-01-01'),
('Wireless Mouse Pro','Electronics','Peripherals',12,49.99,'PeriphHub','2021-03-01'),
('Wireless Mouse Basic','Electronics','Peripherals',6,24.99,'PeriphHub','2021-03-01'),
('USB-C Hub 7-port','Electronics','Peripherals',18,79.99,'ConnectPro','2022-05-01'),
('USB-C Hub 4-port','Electronics','Peripherals',10,39.99,'ConnectPro','2022-05-01'),
('Mechanical Keyboard RGB','Electronics','Peripherals',40,129.99,'KeyMasters','2021-08-01'),
('Mechanical Keyboard TKL','Electronics','Peripherals',35,99.99,'KeyMasters','2022-01-01'),
('Membrane Keyboard','Electronics','Peripherals',10,39.99,'KeyMasters','2023-03-01'),
('Monitor 27" 4K','Electronics','Displays',200,599.99,'DisplayCo','2021-01-01'),
('Monitor 27" FHD','Electronics','Displays',130,349.99,'DisplayCo','2021-01-01'),
('Monitor 24" FHD','Electronics','Displays',100,249.99,'DisplayCo','2022-03-01'),
('Webcam 4K','Electronics','Peripherals',35,119.99,'CamTech','2022-01-01'),
('Webcam 1080p','Electronics','Peripherals',20,69.99,'CamTech','2021-06-01'),
('Headphones ANC Pro','Electronics','Audio',80,299.99,'SoundWave','2021-04-01'),
('Headphones ANC Basic','Electronics','Audio',50,179.99,'SoundWave','2022-01-01'),
('Earbuds Wireless Pro','Electronics','Audio',40,149.99,'SoundWave','2022-06-01'),
('Earbuds Wireless Basic','Electronics','Audio',20,79.99,'SoundWave','2023-01-01'),
('Tablet 12"','Electronics','Tablets',150,499.99,'TechCorp','2022-03-01'),
('Tablet 10"','Electronics','Tablets',100,349.99,'TechCorp','2022-03-01'),
('Tablet 8"','Electronics','Tablets',70,249.99,'TechCorp','2023-01-01'),
('Smartwatch Pro','Electronics','Wearables',80,299.99,'WearTech','2022-01-01'),
('Smartwatch Basic','Electronics','Wearables',40,149.99,'WearTech','2022-06-01'),
('Portable Charger 20000','Electronics','Accessories',15,59.99,'PowerUp','2021-01-01'),
('Portable Charger 10000','Electronics','Accessories',8,34.99,'PowerUp','2021-01-01'),
('Phone Stand Adjustable','Electronics','Accessories',5,19.99,'DeskGear','2022-01-01'),
('Laptop Stand Foldable','Electronics','Accessories',12,44.99,'DeskGear','2022-01-01'),
('Cable USB-C 2m','Electronics','Accessories',3,14.99,'ConnectPro','2021-01-01'),
('Cable HDMI 2m','Electronics','Accessories',5,19.99,'ConnectPro','2021-01-01'),
('Ergonomic Chair Pro','Furniture','Seating',280,799.99,'ErgoFurn','2020-06-01'),
('Ergonomic Chair Standard','Furniture','Seating',180,499.99,'ErgoFurn','2021-01-01'),
('Task Chair Basic','Furniture','Seating',90,249.99,'ErgoFurn','2022-01-01'),
('Standing Desk Electric 60"','Furniture','Desks',350,999.99,'DeskMakers','2021-01-01'),
('Standing Desk Manual 48"','Furniture','Desks',200,599.99,'DeskMakers','2021-06-01'),
('Fixed Desk 60"','Furniture','Desks',120,349.99,'DeskMakers','2022-01-01'),
('Bookshelf 5-Tier','Furniture','Storage',100,299.99,'ShelfCo','2021-01-01'),
('Bookshelf 3-Tier','Furniture','Storage',60,179.99,'ShelfCo','2022-01-01'),
('Filing Cabinet 4-Drawer','Furniture','Storage',120,349.99,'ShelfCo','2021-01-01'),
('Filing Cabinet 2-Drawer','Furniture','Storage',70,199.99,'ShelfCo','2022-01-01'),
('Whiteboard 4x3','Furniture','Office Accessories',50,149.99,'OfficePro','2021-01-01'),
('Whiteboard 6x4','Furniture','Office Accessories',80,249.99,'OfficePro','2021-01-01'),
('Desk Lamp LED Dimmable','Furniture','Lighting',25,79.99,'BrightHome','2021-01-01'),
('Desk Lamp Basic','Furniture','Lighting',10,29.99,'BrightHome','2022-01-01'),
('Monitor Arm Dual','Furniture','Mounts',40,129.99,'MountPro','2022-01-01'),
('Monitor Arm Single','Furniture','Mounts',25,79.99,'MountPro','2022-01-01'),
('Notebook Premium A4 (Pack 5)','Stationery','Paper',8,24.99,'PaperCo','2021-01-01'),
('Notebook Basic A4 (Pack 10)','Stationery','Paper',6,14.99,'PaperCo','2021-01-01'),
('Pen Set Luxury 12','Stationery','Writing',12,34.99,'InkMasters','2021-01-01'),
('Pen Set Standard 24','Stationery','Writing',6,14.99,'InkMasters','2022-01-01'),
('Marker Set 20 Colors','Stationery','Writing',8,19.99,'InkMasters','2022-01-01'),
('Sticky Notes 12-pack','Stationery','Office Supplies',4,9.99,'PaperCo','2021-01-01'),
('Planner 2025 Premium','Stationery','Planning',15,39.99,'PaperCo','2025-01-01'),
('Planner 2025 Basic','Stationery','Planning',7,17.99,'PaperCo','2025-01-01'),
('Binder A4 Pack 5','Stationery','Office Supplies',8,19.99,'PaperCo','2022-01-01'),
('Stapler Heavy Duty','Stationery','Office Supplies',12,29.99,'OfficePro','2021-01-01'),
('Coffee Maker Espresso Pro','Appliances','Coffee',60,199.99,'BrewMaster','2021-06-01'),
('Coffee Maker Drip','Appliances','Coffee',35,99.99,'BrewMaster','2022-01-01'),
('Coffee Maker Pod','Appliances','Coffee',45,149.99,'BrewMaster','2022-06-01'),
('Water Purifier UV','Appliances','Water',120,349.99,'PureWater','2021-01-01'),
('Water Purifier RO','Appliances','Water',180,499.99,'PureWater','2022-01-01'),
('Air Purifier HEPA Large','Appliances','Air',90,299.99,'CleanAir','2021-01-01'),
('Air Purifier HEPA Small','Appliances','Air',50,149.99,'CleanAir','2022-01-01'),
('Desk Fan 12"','Appliances','Climate',18,59.99,'CoolBreeze','2021-01-01'),
('Desk Fan 8"','Appliances','Climate',10,34.99,'CoolBreeze','2022-01-01'),
('Mini Fridge 20L','Appliances','Refrigeration',80,229.99,'CoolTech','2022-01-01'),
('Mini Fridge 10L','Appliances','Refrigeration',50,149.99,'CoolTech','2023-01-01'),
('Microwave Compact','Appliances','Kitchen',60,189.99,'HomeApp','2022-01-01'),
('Electric Kettle','Appliances','Kitchen',20,59.99,'HomeApp','2021-01-01'),
('Toaster 4-Slice','Appliances','Kitchen',25,69.99,'HomeApp','2022-01-01'),
('Blender Pro','Appliances','Kitchen',40,129.99,'HomeApp','2022-06-01'),
('Shredder 10-Sheet','Electronics','Office Equipment',50,149.99,'OfficeTech','2021-01-01'),
('Shredder 6-Sheet','Electronics','Office Equipment',30,89.99,'OfficeTech','2022-01-01'),
('Printer Laser Mono','Electronics','Printing',150,449.99,'PrintPro','2021-01-01'),
('Printer Inkjet Color','Electronics','Printing',80,249.99,'PrintPro','2022-01-01'),
('Scanner Flatbed A4','Electronics','Printing',70,199.99,'PrintPro','2022-01-01'),
('External SSD 1TB','Electronics','Storage Devices',70,199.99,'DataDrive','2022-01-01'),
('External SSD 500GB','Electronics','Storage Devices',40,119.99,'DataDrive','2022-01-01'),
('External HDD 2TB','Electronics','Storage Devices',50,129.99,'DataDrive','2021-06-01'),
('USB Flash Drive 128GB','Electronics','Storage Devices',8,29.99,'DataDrive','2022-01-01'),
('USB Flash Drive 64GB','Electronics','Storage Devices',4,14.99,'DataDrive','2022-01-01'),
('Smart Speaker Large','Electronics','Smart Home',60,199.99,'SmartHome','2022-01-01'),
('Smart Speaker Mini','Electronics','Smart Home',30,99.99,'SmartHome','2022-06-01'),
('Smart Plug 4-Pack','Electronics','Smart Home',20,49.99,'SmartHome','2022-01-01'),
('Security Camera Indoor','Electronics','Smart Home',40,129.99,'SmartHome','2022-06-01'),
('Security Camera Outdoor','Electronics','Smart Home',60,189.99,'SmartHome','2023-01-01'),
('Desk Organizer Premium','Furniture','Office Accessories',18,49.99,'DeskGear','2022-01-01'),
('Desk Organizer Basic','Furniture','Office Accessories',8,22.99,'DeskGear','2022-01-01'),
('Cable Management Kit','Electronics','Accessories',10,29.99,'ConnectPro','2022-01-01'),
('Webcam Ring Light','Electronics','Accessories',15,44.99,'CamTech','2022-06-01'),
('Green Screen Collapsible','Electronics','Accessories',25,69.99,'CamTech','2023-01-01'),
('Ergonomic Mouse Vertical','Electronics','Peripherals',25,79.99,'PeriphHub','2022-06-01'),
('Trackpad Wireless','Electronics','Peripherals',30,89.99,'PeriphHub','2023-01-01'),
('Numeric Keypad Wireless','Electronics','Peripherals',15,44.99,'KeyMasters','2023-01-01'),
('Document Holder','Furniture','Office Accessories',10,27.99,'DeskGear','2022-01-01'),
('Footrest Ergonomic','Furniture','Seating',30,89.99,'ErgoFurn','2022-06-01');

-- ── CUSTOMERS (expand schema and reload with 500 rows via GENERATOR) ──────
CREATE TABLE IF NOT EXISTS CUSTOMERS (
    CUSTOMER_ID INT AUTOINCREMENT PRIMARY KEY,
    FIRST_NAME  VARCHAR(100),
    LAST_NAME   VARCHAR(100),
    EMAIL       VARCHAR(200),
    PHONE       VARCHAR(20),
    REGION      VARCHAR(50),
    STATE       VARCHAR(30),
    SEGMENT     VARCHAR(50),
    CHANNEL_ID  INT,
    SIGNUP_DATE DATE,
    CREATED_AT  TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- Add columns that may not exist from 02_sales_data.sql
ALTER TABLE CUSTOMERS ADD COLUMN IF NOT EXISTS PHONE VARCHAR(20);
ALTER TABLE CUSTOMERS ADD COLUMN IF NOT EXISTS STATE VARCHAR(30);
ALTER TABLE CUSTOMERS ADD COLUMN IF NOT EXISTS CHANNEL_ID INT;
ALTER TABLE CUSTOMERS ADD COLUMN IF NOT EXISTS SIGNUP_DATE DATE;

TRUNCATE TABLE CUSTOMERS;

INSERT INTO CUSTOMERS (FIRST_NAME, LAST_NAME, EMAIL, PHONE, REGION, STATE, SEGMENT, CHANNEL_ID, SIGNUP_DATE)
SELECT
    CASE MOD(SEQ4(),20)
        WHEN 0 THEN 'Alice'   WHEN 1 THEN 'Bob'     WHEN 2 THEN 'Carol'   WHEN 3 THEN 'David'
        WHEN 4 THEN 'Eva'     WHEN 5 THEN 'Frank'   WHEN 6 THEN 'Grace'   WHEN 7 THEN 'Henry'
        WHEN 8 THEN 'Iris'    WHEN 9 THEN 'Jack'    WHEN 10 THEN 'Karen'  WHEN 11 THEN 'Leo'
        WHEN 12 THEN 'Mia'    WHEN 13 THEN 'Nathan' WHEN 14 THEN 'Olivia' WHEN 15 THEN 'Paul'
        WHEN 16 THEN 'Quinn'  WHEN 17 THEN 'Rachel' WHEN 18 THEN 'Steve'  ELSE 'Tina'
    END AS FIRST_NAME,
    CASE MOD(SEQ4(),15)
        WHEN 0 THEN 'Johnson'  WHEN 1 THEN 'Smith'    WHEN 2 THEN 'Williams' WHEN 3 THEN 'Brown'
        WHEN 4 THEN 'Davis'    WHEN 5 THEN 'Miller'   WHEN 6 THEN 'Wilson'   WHEN 7 THEN 'Moore'
        WHEN 8 THEN 'Taylor'   WHEN 9 THEN 'Anderson' WHEN 10 THEN 'Thomas'  WHEN 11 THEN 'Jackson'
        WHEN 12 THEN 'White'   WHEN 13 THEN 'Harris'  ELSE 'Martin'
    END AS LAST_NAME,
    'customer' || SEQ4() || '@email.com' AS EMAIL,
    '555-' || LPAD(UNIFORM(1000,9999,RANDOM())::VARCHAR,4,'0') AS PHONE,
    CASE MOD(UNIFORM(1,100,RANDOM()),4) WHEN 0 THEN 'North' WHEN 1 THEN 'South' WHEN 2 THEN 'East' ELSE 'West' END AS REGION,
    CASE MOD(UNIFORM(1,10,RANDOM()),10)
        WHEN 0 THEN 'NY' WHEN 1 THEN 'CA' WHEN 2 THEN 'TX' WHEN 3 THEN 'FL' WHEN 4 THEN 'IL'
        WHEN 5 THEN 'WA' WHEN 6 THEN 'GA' WHEN 7 THEN 'NC' WHEN 8 THEN 'OH' ELSE 'CO'
    END AS STATE,
    CASE MOD(UNIFORM(1,10,RANDOM()),3) WHEN 0 THEN 'Enterprise' WHEN 1 THEN 'Mid-Market' ELSE 'SMB' END AS SEGMENT,
    UNIFORM(1,5,RANDOM()) AS CHANNEL_ID,
    DATEADD(DAY, -UNIFORM(30,1095,RANDOM()), CURRENT_DATE()) AS SIGNUP_DATE
FROM TABLE(GENERATOR(ROWCOUNT => 500));

-- ── ORDERS (5000 rows via GENERATOR) ─────────────────────
CREATE TABLE IF NOT EXISTS ORDERS (
    ORDER_ID        INT AUTOINCREMENT PRIMARY KEY,
    CUSTOMER_ID     INT REFERENCES CUSTOMERS(CUSTOMER_ID),
    STORE_ID        INT,
    CHANNEL_ID      INT,
    PROMO_ID        INT,
    ORDER_DATE      DATE,
    SHIP_DATE       DATE,
    DELIVERY_DATE   DATE,
    STATUS          VARCHAR(20),
    SUBTOTAL        DECIMAL(12,2),
    DISCOUNT_AMOUNT DECIMAL(10,2),
    TAX_AMOUNT      DECIMAL(10,2),
    TOTAL_AMOUNT    DECIMAL(12,2),
    PAYMENT_METHOD  VARCHAR(30)
);

-- Add columns that may not exist from 02_sales_data.sql
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS STORE_ID INT;
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS CHANNEL_ID INT;
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS PROMO_ID INT;
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS SHIP_DATE DATE;
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS DELIVERY_DATE DATE;
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS SUBTOTAL DECIMAL(12,2);
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS DISCOUNT_AMOUNT DECIMAL(10,2);
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS TAX_AMOUNT DECIMAL(10,2);
ALTER TABLE ORDERS ADD COLUMN IF NOT EXISTS PAYMENT_METHOD VARCHAR(30);

TRUNCATE TABLE ORDERS;

INSERT INTO ORDERS (CUSTOMER_ID,STORE_ID,CHANNEL_ID,PROMO_ID,ORDER_DATE,SHIP_DATE,DELIVERY_DATE,STATUS,SUBTOTAL,DISCOUNT_AMOUNT,TAX_AMOUNT,TOTAL_AMOUNT,PAYMENT_METHOD)
SELECT
    UNIFORM(1,500,RANDOM())   AS CUSTOMER_ID,
    UNIFORM(1,20,RANDOM())    AS STORE_ID,
    UNIFORM(1,5,RANDOM())     AS CHANNEL_ID,
    IFF(UNIFORM(1,5,RANDOM())=1, UNIFORM(1,15,RANDOM()), NULL) AS PROMO_ID,
    DATEADD(DAY, -UNIFORM(0,730,RANDOM()), CURRENT_DATE()) AS ORDER_DATE,
    DATEADD(DAY, UNIFORM(1,3,RANDOM()),  DATEADD(DAY,-UNIFORM(0,730,RANDOM()),CURRENT_DATE())) AS SHIP_DATE,
    DATEADD(DAY, UNIFORM(4,10,RANDOM()), DATEADD(DAY,-UNIFORM(0,730,RANDOM()),CURRENT_DATE())) AS DELIVERY_DATE,
    CASE UNIFORM(1,10,RANDOM()) WHEN 1 THEN 'Processing' WHEN 2 THEN 'Shipped' WHEN 3 THEN 'Cancelled' ELSE 'Completed' END AS STATUS,
    ROUND(UNIFORM(20,2000,RANDOM())::DECIMAL(12,2),2) AS SUBTOTAL,
    ROUND(UNIFORM(0,200,RANDOM())::DECIMAL(10,2),2)   AS DISCOUNT_AMOUNT,
    ROUND(UNIFORM(2,160,RANDOM())::DECIMAL(10,2),2)   AS TAX_AMOUNT,
    ROUND(SUBTOTAL - DISCOUNT_AMOUNT + TAX_AMOUNT, 2) AS TOTAL_AMOUNT,
    CASE UNIFORM(1,5,RANDOM()) WHEN 1 THEN 'Credit Card' WHEN 2 THEN 'Debit Card' WHEN 3 THEN 'PayPal' WHEN 4 THEN 'Bank Transfer' ELSE 'Buy Now Pay Later' END AS PAYMENT_METHOD
FROM TABLE(GENERATOR(ROWCOUNT => 5000));

-- ── ORDER_ITEMS (15000 rows) ──────────────────────────────
CREATE TABLE IF NOT EXISTS ORDER_ITEMS (
    ORDER_ITEM_ID INT AUTOINCREMENT PRIMARY KEY,
    ORDER_ID      INT REFERENCES ORDERS(ORDER_ID),
    PRODUCT_ID    INT REFERENCES PRODUCTS(PRODUCT_ID),
    QUANTITY      INT,
    UNIT_PRICE    DECIMAL(10,2),
    DISCOUNT_PCT  DECIMAL(5,2),
    LINE_TOTAL    DECIMAL(12,2)
);

-- Add columns that may not exist from 02_sales_data.sql
ALTER TABLE ORDER_ITEMS ADD COLUMN IF NOT EXISTS DISCOUNT_PCT DECIMAL(5,2);
ALTER TABLE ORDER_ITEMS ADD COLUMN IF NOT EXISTS LINE_TOTAL DECIMAL(12,2);

TRUNCATE TABLE ORDER_ITEMS;

INSERT INTO ORDER_ITEMS (ORDER_ID,PRODUCT_ID,QUANTITY,UNIT_PRICE,DISCOUNT_PCT,LINE_TOTAL)
SELECT
    UNIFORM(1,5000,RANDOM())    AS ORDER_ID,
    UNIFORM(1,96,RANDOM())      AS PRODUCT_ID,
    UNIFORM(1,5,RANDOM())       AS QUANTITY,
    ROUND(UNIFORM(10,1300,RANDOM())::DECIMAL(10,2),2) AS UNIT_PRICE,
    ROUND(IFF(UNIFORM(1,4,RANDOM())=1, UNIFORM(5,30,RANDOM()), 0)::DECIMAL(5,2),2) AS DISCOUNT_PCT,
    ROUND(QUANTITY * UNIT_PRICE * (1 - DISCOUNT_PCT/100.0), 2) AS LINE_TOTAL
FROM TABLE(GENERATOR(ROWCOUNT => 15000));

-- ── RETURNS (1500 rows) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS RETURNS (
    RETURN_ID       INT AUTOINCREMENT PRIMARY KEY,
    ORDER_ITEM_ID   INT,
    ORDER_ID        INT,
    PRODUCT_ID      INT REFERENCES PRODUCTS(PRODUCT_ID),
    RETURN_DATE     DATE,
    RETURN_REASON   VARCHAR(50),
    RETURN_STATUS   VARCHAR(20),
    REFUND_AMOUNT   DECIMAL(10,2)
);

INSERT INTO RETURNS (ORDER_ITEM_ID,ORDER_ID,PRODUCT_ID,RETURN_DATE,RETURN_REASON,RETURN_STATUS,REFUND_AMOUNT)
SELECT
    UNIFORM(1,15000,RANDOM())   AS ORDER_ITEM_ID,
    UNIFORM(1,5000,RANDOM())    AS ORDER_ID,
    UNIFORM(1,96,RANDOM())      AS PRODUCT_ID,
    DATEADD(DAY, -UNIFORM(0,700,RANDOM()), CURRENT_DATE()) AS RETURN_DATE,
    CASE UNIFORM(1,6,RANDOM())
        WHEN 1 THEN 'Defective'         WHEN 2 THEN 'Wrong Item'
        WHEN 3 THEN 'Changed Mind'      WHEN 4 THEN 'Damaged in Shipping'
        WHEN 5 THEN 'Not as Described'  ELSE 'Better Price Found'
    END AS RETURN_REASON,
    CASE UNIFORM(1,3,RANDOM()) WHEN 1 THEN 'Pending' WHEN 2 THEN 'Approved' ELSE 'Completed' END AS RETURN_STATUS,
    ROUND(UNIFORM(10,1500,RANDOM())::DECIMAL(10,2),2) AS REFUND_AMOUNT
FROM TABLE(GENERATOR(ROWCOUNT => 1500));

-- ── INVENTORY (10000 rows: product x store x date) ────────
CREATE TABLE IF NOT EXISTS INVENTORY (
    INVENTORY_ID    INT AUTOINCREMENT PRIMARY KEY,
    PRODUCT_ID      INT,
    STORE_ID        INT,
    SNAPSHOT_DATE   DATE,
    QUANTITY_ON_HAND INT,
    QUANTITY_RESERVED INT,
    REORDER_POINT   INT,
    LAST_RESTOCKED  DATE
);

INSERT INTO INVENTORY (PRODUCT_ID,STORE_ID,SNAPSHOT_DATE,QUANTITY_ON_HAND,QUANTITY_RESERVED,REORDER_POINT,LAST_RESTOCKED)
SELECT
    UNIFORM(1,96,RANDOM())      AS PRODUCT_ID,
    UNIFORM(1,20,RANDOM())      AS STORE_ID,
    DATEADD(DAY, -UNIFORM(0,90,RANDOM()), CURRENT_DATE()) AS SNAPSHOT_DATE,
    UNIFORM(0,500,RANDOM())     AS QUANTITY_ON_HAND,
    UNIFORM(0,50,RANDOM())      AS QUANTITY_RESERVED,
    UNIFORM(10,50,RANDOM())     AS REORDER_POINT,
    DATEADD(DAY, -UNIFORM(0,30,RANDOM()), CURRENT_DATE()) AS LAST_RESTOCKED
FROM TABLE(GENERATOR(ROWCOUNT => 10000));
