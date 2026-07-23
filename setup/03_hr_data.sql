-- ============================================================
-- 03_hr_data.sql
-- HR schema: Departments, Employees
-- ============================================================

USE DATABASE CONVERSATIONAL_BI;
USE SCHEMA HR;
USE WAREHOUSE BI_ASSISTANT_WH;

-- Departments table
CREATE OR REPLACE TABLE DEPARTMENTS (
    DEPT_ID INT AUTOINCREMENT PRIMARY KEY,
    DEPT_NAME VARCHAR(100) NOT NULL,
    ANNUAL_BUDGET DECIMAL(12,2),
    LOCATION VARCHAR(100)
);

-- Employees table
CREATE OR REPLACE TABLE EMPLOYEES (
    EMP_ID INT AUTOINCREMENT PRIMARY KEY,
    FIRST_NAME VARCHAR(100),
    LAST_NAME VARCHAR(100),
    EMAIL VARCHAR(200),
    DEPT_ID INT REFERENCES DEPARTMENTS(DEPT_ID),
    JOB_TITLE VARCHAR(150),
    HIRE_DATE DATE,
    SALARY DECIMAL(10,2),
    STATUS VARCHAR(20) DEFAULT 'Active'
);

-- ============================================================
-- Sample Data: Departments
-- ============================================================
INSERT INTO DEPARTMENTS (DEPT_NAME, ANNUAL_BUDGET, LOCATION) VALUES
('Engineering', 2500000.00, 'San Francisco'),
('Sales', 1800000.00, 'New York'),
('Marketing', 1200000.00, 'New York'),
('Human Resources', 800000.00, 'Chicago'),
('Finance', 1000000.00, 'Chicago'),
('Operations', 1500000.00, 'San Francisco');

-- ============================================================
-- Sample Data: Employees
-- ============================================================
INSERT INTO EMPLOYEES (FIRST_NAME, LAST_NAME, EMAIL, DEPT_ID, JOB_TITLE, HIRE_DATE, SALARY, STATUS) VALUES
('James', 'Peterson', 'james.peterson@company.com', 1, 'Senior Software Engineer', '2020-03-15', 145000.00, 'Active'),
('Sarah', 'Chen', 'sarah.chen@company.com', 1, 'Staff Engineer', '2019-06-01', 175000.00, 'Active'),
('Michael', 'Kumar', 'michael.kumar@company.com', 1, 'Software Engineer', '2022-01-10', 115000.00, 'Active'),
('Emily', 'Rodriguez', 'emily.rodriguez@company.com', 1, 'Engineering Manager', '2018-09-20', 185000.00, 'Active'),
('Daniel', 'Park', 'daniel.park@company.com', 1, 'Junior Developer', '2024-02-01', 85000.00, 'Active'),
('Jessica', 'Lee', 'jessica.lee@company.com', 1, 'DevOps Engineer', '2021-07-15', 135000.00, 'Active'),
('Robert', 'Singh', 'robert.singh@company.com', 1, 'Data Engineer', '2021-11-01', 140000.00, 'Active'),
('Amanda', 'Foster', 'amanda.foster@company.com', 1, 'QA Engineer', '2022-05-20', 105000.00, 'Active'),
('Chris', 'Wang', 'chris.wang@company.com', 2, 'Sales Director', '2019-01-15', 160000.00, 'Active'),
('Laura', 'Martinez', 'laura.martinez@company.com', 2, 'Account Executive', '2020-08-01', 95000.00, 'Active'),
('Kevin', 'O''Brien', 'kevin.obrien@company.com', 2, 'Sales Representative', '2022-03-10', 75000.00, 'Active'),
('Nicole', 'Thompson', 'nicole.thompson@company.com', 2, 'Account Executive', '2021-06-15', 98000.00, 'Active'),
('Ryan', 'Davis', 'ryan.davis@company.com', 2, 'Sales Manager', '2019-11-01', 130000.00, 'Active'),
('Angela', 'Kim', 'angela.kim@company.com', 2, 'Business Development Rep', '2023-01-15', 70000.00, 'Active'),
('Tom', 'Baker', 'tom.baker@company.com', 2, 'Sales Representative', '2023-09-01', 72000.00, 'Active'),
('Samantha', 'Green', 'samantha.green@company.com', 3, 'Marketing Director', '2018-04-01', 155000.00, 'Active'),
('Brandon', 'Cole', 'brandon.cole@company.com', 3, 'Content Manager', '2021-02-15', 90000.00, 'Active'),
('Diana', 'Patel', 'diana.patel@company.com', 3, 'Digital Marketing Specialist', '2022-07-01', 82000.00, 'Active'),
('Marcus', 'Hall', 'marcus.hall@company.com', 3, 'SEO Analyst', '2023-03-20', 75000.00, 'Active'),
('Priya', 'Sharma', 'priya.sharma@company.com', 3, 'Brand Manager', '2020-10-01', 105000.00, 'Active'),
('Linda', 'Wright', 'linda.wright@company.com', 4, 'HR Director', '2017-06-01', 145000.00, 'Active'),
('George', 'Adams', 'george.adams@company.com', 4, 'HR Business Partner', '2020-01-15', 95000.00, 'Active'),
('Helen', 'Scott', 'helen.scott@company.com', 4, 'Recruiter', '2022-04-01', 72000.00, 'Active'),
('Victor', 'Nelson', 'victor.nelson@company.com', 4, 'HR Coordinator', '2023-08-15', 62000.00, 'Active'),
('Catherine', 'Young', 'catherine.young@company.com', 5, 'CFO', '2016-03-01', 220000.00, 'Active'),
('Andrew', 'Carter', 'andrew.carter@company.com', 5, 'Financial Analyst', '2021-09-01', 95000.00, 'Active'),
('Michelle', 'Rivera', 'michelle.rivera@company.com', 5, 'Accountant', '2020-05-15', 82000.00, 'Active'),
('Derek', 'Phillips', 'derek.phillips@company.com', 5, 'Senior Accountant', '2019-12-01', 98000.00, 'Active'),
('Sophia', 'Morgan', 'sophia.morgan@company.com', 5, 'Payroll Specialist', '2022-02-01', 68000.00, 'Active'),
('Patrick', 'Reed', 'patrick.reed@company.com', 6, 'VP Operations', '2017-10-01', 175000.00, 'Active'),
('Monica', 'Flores', 'monica.flores@company.com', 6, 'Operations Manager', '2020-04-15', 115000.00, 'Active'),
('Jason', 'Cooper', 'jason.cooper@company.com', 6, 'Supply Chain Analyst', '2021-08-01', 88000.00, 'Active'),
('Rebecca', 'Ward', 'rebecca.ward@company.com', 6, 'Logistics Coordinator', '2022-11-01', 72000.00, 'Active'),
('Tyler', 'Brooks', 'tyler.brooks@company.com', 6, 'Facilities Manager', '2023-05-01', 78000.00, 'Active'),
('Olivia', 'Bennett', 'olivia.bennett@company.com', 1, 'Software Engineer', '2023-06-15', 110000.00, 'Active'),
('Nathan', 'Gray', 'nathan.gray@company.com', 2, 'Sales Representative', '2024-01-10', 70000.00, 'Active'),
('Zoe', 'Murphy', 'zoe.murphy@company.com', 3, 'Social Media Manager', '2023-11-01', 78000.00, 'Active'),
('Ethan', 'Cox', 'ethan.cox@company.com', 6, 'Operations Analyst', '2024-03-01', 80000.00, 'Active'),
('Maya', 'Russell', 'maya.russell@company.com', 1, 'Frontend Developer', '2022-09-15', 120000.00, 'Active'),
('Luke', 'Howard', 'luke.howard@company.com', 2, 'Sales Engineer', '2021-04-01', 125000.00, 'Active'),
('Isabella', 'Torres', 'isabella.torres@company.com', 3, 'Marketing Analyst', '2023-07-15', 76000.00, 'Active'),
('Aaron', 'Butler', 'aaron.butler@company.com', 4, 'Training Specialist', '2021-10-01', 78000.00, 'Active'),
('Hannah', 'Price', 'hannah.price@company.com', 5, 'Budget Analyst', '2023-04-01', 85000.00, 'Active'),
('Caleb', 'Long', 'caleb.long@company.com', 6, 'Project Manager', '2020-07-01', 110000.00, 'Active'),
('Grace', 'Hughes', 'grace.hughes@company.com', 1, 'Backend Developer', '2021-03-15', 130000.00, 'Active'),
('Jake', 'Simmons', 'jake.simmons@company.com', 2, 'Sales Analyst', '2022-12-01', 80000.00, 'Active'),
('Lily', 'Foster', 'lily.foster@company.com', 3, 'Event Coordinator', '2024-01-15', 65000.00, 'Active'),
('Evan', 'Stone', 'evan.stone@company.com', 6, 'Warehouse Supervisor', '2019-08-01', 72000.00, 'Active'),
('Chloe', 'Dixon', 'chloe.dixon@company.com', 1, 'UX Designer', '2022-06-01', 115000.00, 'Active'),
('Alex', 'Freeman', 'alex.freeman@company.com', 5, 'Tax Specialist', '2020-11-15', 92000.00, 'Active');
