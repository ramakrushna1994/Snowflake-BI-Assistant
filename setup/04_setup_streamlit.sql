-- ============================================================
-- 04_setup_streamlit.sql
-- Create Streamlit app in Snowflake
-- ============================================================

USE ROLE ACCOUNTADMIN;
USE DATABASE CONVERSATIONAL_BI;
USE WAREHOUSE BI_ASSISTANT_WH;

-- Create a schema for the app
CREATE SCHEMA IF NOT EXISTS APP;

-- Create a stage to hold the Streamlit app code
CREATE STAGE IF NOT EXISTS APP.STREAMLIT_STAGE
    DIRECTORY = (ENABLE = TRUE);

-- Upload the app file to stage (run from SnowSQL or Snowsight):
-- PUT file://app/streamlit_app.py @CONVERSATIONAL_BI.APP.STREAMLIT_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;

-- Create the Streamlit app
CREATE OR REPLACE STREAMLIT APP.CONVERSATIONAL_BI_ASSISTANT
    ROOT_LOCATION = '@CONVERSATIONAL_BI.APP.STREAMLIT_STAGE'
    MAIN_FILE = 'streamlit_app.py'
    QUERY_WAREHOUSE = 'BI_ASSISTANT_WH'
    TITLE = 'Conversational BI Assistant';

-- Grant access if needed
-- GRANT USAGE ON STREAMLIT APP.CONVERSATIONAL_BI_ASSISTANT TO ROLE <role_name>;
