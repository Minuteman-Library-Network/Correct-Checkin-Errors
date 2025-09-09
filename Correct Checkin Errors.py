from sierra_ils_utils import SierraAPI
import json
import configparser
import psycopg2
import os
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import gspread

def runquery(query):
    config = configparser.ConfigParser()
    config.read('C:\\my_file.ini')
    '''
    .ini file contains connection_string for Sierra SQL in the following form
    [sql]
    connection_string = dbname='iii' user='' host='' password='' port=1032
    '''
    
    try:
	    conn = psycopg2.connect( config['sql']['connection_string'] )
    except:
        print("unable to connect to the database")
        clear_connection()
        return
        
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    return rows

#Uses items/checkouts/ API endpoint to check item in again    
def checkin_item(barcode,username,statgroup,sierra_api):
    url = "items/checkouts/" + barcode + "?username=" + username + "&statgroup=" + statgroup
    request = sierra_api.request('DELETE',url)
    request.raise_for_status()

#log items that were corrected to an existing Google Sheet    
def appendToSheet(spreadSheetId, data):
    scopes = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('GSheet Keyfile.json', scopes)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    request = service.spreadsheets().values().append(
        spreadsheetId=spreadSheetId, range='A1:Z1',
        valueInputOption='USER_ENTERED' ,body={'values': data})
    result = request.execute() 

def main():
    config = configparser.ConfigParser()
    config.read('C:\\my_file.ini')

    '''
    .ini file contains url/key/secret for the api in the following form
    [api]
    base_url = https://[local domain]/iii/sierra-api/v6
    client_key = [enter Sierra API key]
    client_secret = [enter Sierra API secret]
    '''

    base_url = config['api']['base_url'] + '/'
    #note sierra-ils-utils assumes base_url contains the trailing /, which the file I have been using did not contain so it is appended here
    client_key = config['api']['client_key']
    client_secret = config['api']['client_secret']
    
    #launch SierraAPI session
    sierra_api = SierraAPI(base_url,client_key,client_secret)
    sierra_api.request('GET','info/token')
	
	#query to identify items that are simultaneously checked out and in transit, retrieve data needed for corrections and logging
    error_query = """\
            SELECT
              ip.barcode,
              si.name AS username,
              si.code AS checkin_stat_group_code,
              i.checkout_statistic_group_code_num AS checkout_stat_group_code,
              so.name AS checkout_stat_group_name,
              v.field_content AS message,
              --Converting timestamps to varchar because timestamps are not serializable and led to errors when adding log entries
              o.checkout_gmt::VARCHAR AS checkout_time,
              TO_TIMESTAMP(SPLIT_PART(v.field_content,': IN',1), 'Dy Mon DD YYYY  HH:MIAM')::VARCHAR AS checkin_time,
              SPLIT_PART(SPLIT_PART(v.field_content,'from ',2),' to',1) AS origin_loc,
              SPLIT_PART(v.field_content,'to ',2) AS destination_loc,
              CASE
                WHEN h.id IS NOT NULL THEN true
	            ELSE FALSE
              END AS fulfilling_hold
  
             FROM sierra_view.item_record i
             JOIN sierra_view.checkout o
               ON i.id = o.item_record_id
             JOIN sierra_view.varfield v
               ON i.id = v.record_id
               AND v.varfield_type_code = 'm'
               AND v.field_content LIKE '%IN TRANSIT%'
             JOIN sierra_view.item_record_property ip
               ON i.id = ip.item_record_id
             JOIN sierra_view.statistic_group_myuser so
               ON i.checkout_statistic_group_code_num = so.code
             JOIN sierra_view.statistic_group_myuser si
               ON SPLIT_PART(SPLIT_PART(v.field_content,'from ',2),' to',1) = si.name
             LEFT JOIN sierra_view.hold h
               ON i.id = h.record_id

             WHERE i.item_status_code IN ('t')
               AND EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - TO_TIMESTAMP(SPLIT_PART(v.field_content,': IN',1), 'Dy Mon DD YYYY  HH:MIAM'))) > 120

             ORDER BY TO_TIMESTAMP(SPLIT_PART(v.field_content,': IN',1), 'Dy Mon DD YYYY  HH:MIAM')
            """
    
    item_errors = runquery(error_query)
    appendToSheet('MyGoogleSheetId', item_errors)
    #for each item in the error_query results, check it in again
    for rownum, row in enumerate(item_errors):
        checkin_item(str(row[0]),row[1],str(row[2]),sierra_api)    
                    
main()

