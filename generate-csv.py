import pandas as pd
import os

def generate_csv_with_n_entries(original_csv_path, new_csv_path, n_entries):
    original_csv_path = os.path.expanduser(original_csv_path)
    new_csv_path = os.path.expanduser(new_csv_path)

    # Load the original CSV
    df = pd.read_csv(original_csv_path)
    
    # Calculate the current number of entries
    current_entries = len(df)
    
    if n_entries <= current_entries:
        # If fewer entries are requested, truncate the dataframe
        new_df = df.head(n_entries)
    else:
        # If more entries are requested, repeat the dataframe until the desired number is reached
        repeat_times = -(-n_entries // current_entries)  # Ceiling division to ensure enough repeats
        new_df = pd.concat([df]*repeat_times, ignore_index=True)[:n_entries]  # Concatenate and truncate
    
    # Save the new dataframe to a new CSV
    new_df.to_csv(new_csv_path, index=False)

    file_size_mb = os.path.getsize(new_csv_path) / 1048576
    print(f"Size of the newly created file: {file_size_mb:.2f} MB")

    return new_csv_path

# Example usage
original_csv_path = '~/workspace/metric5/testfiles/happyPath.csv'
n_entries = 100000  # Specify the desired number of entries in the new CSV
new_csv_path = f"~/workspace/metric5/testfiles/happyPath_{n_entries}.csv"

# Generate the new CSV
generated_csv_path = generate_csv_with_n_entries(original_csv_path, new_csv_path, n_entries)
print(f"New CSV file with {n_entries} entries generated at: {generated_csv_path}")

