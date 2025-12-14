"""Helper script to peek into the first few email rows."""

import csv

# open the csv file to read one row at a time
with open('data/raw/emails.csv') as csv_file:
    reader = csv.DictReader(csv_file)
    # enumerate gives simple counter (row_number) plus the row data
    for row_number, row in enumerate(reader, start=1):
        print(f'Row {row_number}')
        print('file:', row['file'])
        # split raw message into lines to show only a few
        text_lines = row['message'].strip().splitlines()
        for line in text_lines[:20]:
            print('   ', line)
        if len(text_lines) > 20:
            print('  ...')
        print('-' * 30)
        if row_number == 5:
            break
