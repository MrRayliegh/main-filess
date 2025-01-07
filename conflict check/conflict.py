import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector
from mysql.connector import Error

# Database connection details
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'research',
    'database': 'alldata'
}

# Create the main application window
class ConflictCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Schedule Conflict Checker")

        # Fetch table names button
        self.fetch_tables_button = tk.Button(root, text="Fetch Table Names", command=self.fetch_table_names)
        self.fetch_tables_button.grid(row=0, column=0, padx=10, pady=10)

        # List of table pairs
        self.table_pairs = []

        # Section to add table pairs
        self.pair_frame = tk.Frame(root)
        self.pair_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10)

        self.add_pair_button = tk.Button(root, text="Add Table Pair", command=self.add_table_pair)
        self.add_pair_button.grid(row=2, column=0, padx=10, pady=10)

        # Button to check conflicts
        self.check_button = tk.Button(root, text="Check Conflicts", command=self.check_conflicts)
        self.check_button.grid(row=3, column=0, padx=10, pady=10)
        # Add this in the initialization section of your app:
        self.status_label = tk.Label(root, text="Ready to check conflicts", relief="sunken", anchor="w")
        self.status_label.grid(row=5, column=0, columnspan=3, padx=10, pady=10, sticky="w")
        # Define a style for the conflict rows
        style = ttk.Style()
        style.configure("conflict", background="red", foreground="white")

        # Frame for the conflict table and scrollbar
        table_frame = tk.Frame(root)
        table_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

        # Table to display conflicts
        self.conflict_table = ttk.Treeview(
            table_frame, 
            columns=(
                "Instructor", "Course", "Room", "Start Time", "End Time", "Day",
                "Conflict Instructor", "Conflict Course", "Conflict Room", 
                "Conflict Start Time", "Conflict End Time", "Conflict Day"
            ), 
            show='headings', 
            selectmode="browse"
        )
        self.conflict_table.pack(side="left", fill="both", expand=True)

        # Define table headers dynamically
        for col in self.conflict_table["columns"]:
            self.conflict_table.heading(col, text=col)


        # Add vertical scrollbar
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.conflict_table.yview)
        vsb.pack(side="right", fill="y")
        self.conflict_table.configure(yscrollcommand=vsb.set)

        # Define table headers
        for col in ["Instructor", "Course", "Room", "Start Time", "End Time", "Day"]:
            self.conflict_table.heading(col, text=col)
            self.conflict_table.column(col, anchor="center", width=100)

    def connect_to_database(self):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                return conn
        except Error as e:
            messagebox.showerror("Database Connection Error", str(e))
        return None

    def fetch_table_names(self):
        conn = self.connect_to_database()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()

            # Store table names
            self.table_names = [table[0] for table in tables]

            if self.table_names:
                messagebox.showinfo("Tables Fetched", "Tables fetched successfully.")
            else:
                messagebox.showinfo("No Tables", "No tables found in the database.")

        except mysql.connector.Error as e:
            messagebox.showerror("Query Error", str(e))
        finally:
            conn.close()

    def add_table_pair(self):
        if not hasattr(self, 'table_names') or not self.table_names:
            messagebox.showerror("Error", "No tables available. Fetch table names first.")
            return

        # Create a new row for the table pair
        pair_frame = tk.Frame(self.pair_frame)
        pair_frame.pack(fill='x', pady=5)

        data_table_combobox = ttk.Combobox(pair_frame, values=self.table_names, width=30)
        data_table_combobox.pack(side='left', padx=5)

        time_table_combobox = ttk.Combobox(pair_frame, values=self.table_names, width=30)
        time_table_combobox.pack(side='left', padx=5)

        self.table_pairs.append((data_table_combobox, time_table_combobox))

    def check_conflicts(self):
        if not self.table_pairs:
            messagebox.showerror("Error", "No table pairs selected.")
            return

        conn = self.connect_to_database()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            # Clear the conflict table first
            for row in self.conflict_table.get_children():
                self.conflict_table.delete(row)

            conflicts_found = 0  # Initialize conflict count
            missing_room_data = []  # To store records with no room
            all_conflicts = []  # To hold all conflicts found

            # If there's only one pair, check within that pair only
            if len(self.table_pairs) == 1:
                data_table_cb, time_table_cb = self.table_pairs[0]
                data_table = data_table_cb.get()
                time_table = time_table_cb.get()

                if not data_table or not time_table:
                    messagebox.showerror("Error", "Please select both data and time tables for the pair.")
                    return

                conflicts = self.check_within_pair(cursor, data_table, time_table, missing_room_data)
                conflicts_found += len(conflicts)
                all_conflicts.extend(conflicts)  # Add conflicts to the list

            # For multiple pairs, check within each pair and across all pairs
            combined_data = []  # To store data for cross-pair conflict check
            for data_table_cb, time_table_cb in self.table_pairs:
                data_table = data_table_cb.get()
                time_table = time_table_cb.get()

                if not data_table or not time_table:
                    messagebox.showerror("Error", "Please select both data and time tables for each pair.")
                    continue

                # Ensure that we only get data that has a room assigned
                query = f"""
                SELECT 
                    t1.instructor_name, 
                    t1.course_name, 
                    t1.room_number, 
                    tt1.start_time, 
                    tt1.end_time, 
                    tt1.day
                FROM {data_table} AS t1
                JOIN {time_table} AS tt1 ON t1.id = tt1.program_schedule_id
                WHERE t1.room_number IS NOT NULL AND t1.room_number != ''
                """
                cursor.execute(query)
                records_with_room = cursor.fetchall()

                # Check conflicts only for records with rooms (exclude missing rooms)
                conflicts = self.check_within_pair(cursor, data_table, time_table, missing_room_data)
                conflicts_found += len(conflicts)
                all_conflicts.extend(conflicts)  # Add conflicts to the list

                combined_data.extend(records_with_room)  # Only add records with room information

            # Now check for across-pair conflicts (only for records that have a room)
            if len(self.table_pairs) > 1:
                conflicts = self.check_across_pairs(combined_data, missing_room_data)
                conflicts_found += len(conflicts)
                all_conflicts.extend(conflicts)  # Add across-pair conflicts

            # Now add conflicts to the table
            for conflict in all_conflicts:
                # Only add conflicts if the record has a room assigned (i.e., ignore no room records)
                if conflict[2]:  # Index 2 corresponds to the room number
                    self.conflict_table.insert('', 'end', values=conflict)

            # Show message based on the conflict result
            if conflicts_found > 0:
                messagebox.showinfo("Conflicts Detected", "Conflicts are detected.")
            else:
                messagebox.showinfo("No Conflicts Detected", "No conflicts detected.")
        
        except mysql.connector.Error as e:
            messagebox.showerror("Query Error", str(e))
        finally:
            conn.close()


    def check_within_pair(self, cursor, data_table, time_table, missing_room_data):
        """Check conflicts within a single pair of tables."""
        conflicts = []

        # Step 1: Check for missing room data (i.e., when room is not assigned)
        query_missing_room = f"""
        SELECT 
            t1.instructor_name, 
            t1.course_name, 
            t1.room_number, 
            tt1.start_time, 
            tt1.end_time, 
            tt1.day
        FROM {data_table} AS t1
        JOIN {time_table} AS tt1 ON t1.id = tt1.program_schedule_id
        WHERE t1.room_number IS NULL;
        """
        cursor.execute(query_missing_room)
        missing_room_data.extend(cursor.fetchall())  # Collect data with no room assigned

        # Step 2: Check for conflicts (same room, overlapping times)
        query_conflicts = f"""
        SELECT 
            t1.instructor_name, 
            t1.course_name, 
            t1.room_number, 
            tt1.start_time, 
            tt1.end_time, 
            tt1.day
        FROM {data_table} AS t1
        JOIN {time_table} AS tt1 ON t1.id = tt1.program_schedule_id
        JOIN {data_table} AS t2 ON t1.id != t2.id
        JOIN {time_table} AS tt2 ON t2.id = tt2.program_schedule_id
        WHERE t1.room_number = t2.room_number
        AND tt1.day = tt2.day
        AND (
            -- Overlap: Schedule 1 starts before Schedule 2 ends, and Schedule 2 starts before Schedule 1 ends
            (tt1.start_time < tt2.end_time AND tt1.end_time > tt2.start_time)
        );
        """
        cursor.execute(query_conflicts)
        conflicts.extend(cursor.fetchall())  # Collect conflicts based on overlap logic

        return conflicts  # Return the list of conflicts or the count of conflicts






    def check_across_pairs(self, combined_data, missing_room_data):
        """Check conflicts across all pairs."""
        # Format: [(instructor_name, course_name, room_number, start_time, end_time, day), ...]
        for i, record1 in enumerate(combined_data):
            for j, record2 in enumerate(combined_data):
                if i >= j:
                    continue  # Avoid duplicate comparisons

                # Check if there's a conflict
                if (
                    record1[2] == record2[2]  # Same room
                    and record1[5] == record2[5]  # Same day
                    and not (
                        (record1[4] == record2[3])  # If end time of one equals the start time of the other (allow no conflict)
                    )
                    and (
                        (record1[3] < record2[4]) and (record1[4] > record2[3])  # If they truly overlap
                    )
                ):
                    # Add to missing_room_data or insert conflict
                    missing_room_data.append(record1)  # Or use insert into your conflict table
                    missing_room_data.append(record2)

        return missing_room_data


# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = ConflictCheckerApp(root)
    root.mainloop()
