import csv

# Tolerance thresholds
epsilon = 0.05
delta = 0.25

def auto_dz_act(theory, experiment):
    deviation = abs(theory - experiment)
    if deviation < epsilon:
        return "0/0"
    elif epsilon <= deviation < delta:
        return "D0/DZ"
    else:
        return "DZ"

# Run algorithm on input CSV
with open('data/example_input.csv', 'r') as infile, open('data/output_result.csv', 'w', newline='') as outfile:
    reader = csv.DictReader(infile)
    writer = csv.DictWriter(outfile, fieldnames=['ID', 'Theory', 'Experiment', 'Code'])
    writer.writeheader()
    for row in reader:
        t = float(row['Theory'])
        e = float(row['Experiment'])
        result = auto_dz_act(t, e)
        writer.writerow({
            'ID': row['ID'],
            'Theory': t,
            'Experiment': e,
            'Code': result
        })
