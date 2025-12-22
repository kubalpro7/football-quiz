import os
import random
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# --- KONFIGURACJA ---
FOLDER_Z_KOSZULKAMI = "MEGA_KOLEKCJA_25_26_CENZURA"

class FootballQuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz Koszulkowy - Multi Ligi (Fix UI)")
        self.root.geometry("600x900")
        self.root.resizable(False, False)

        # Zmienne gry
        self.score = 0
        self.rounds = 0
        self.current_image_path = None
        self.current_correct_team = None
        
        self.leagues_data = {} 
        self.all_images_master = [] 
        self.active_images = [] 
        self.active_teams_list = []
        self.league_vars = {} 

        # 1. Ładowanie danych
        self.load_data()

        if not self.all_images_master:
            messagebox.showerror("Błąd", f"Nie znaleziono folderu '{FOLDER_Z_KOSZULKAMI}'!")
            root.destroy()
            return

        # 2. Budowanie interfejsu
        self.create_widgets()
        
        # 3. Start
        self.apply_league_filter(initial=True)

    def load_data(self):
        print("Indeksowanie danych...")
        if not os.path.exists(FOLDER_Z_KOSZULKAMI):
            return

        for league_folder in os.listdir(FOLDER_Z_KOSZULKAMI):
            league_path = os.path.join(FOLDER_Z_KOSZULKAMI, league_folder)
            
            if os.path.isdir(league_path):
                league_name_clean = league_folder.replace("_", " ")
                self.leagues_data[league_name_clean] = []
                self.league_vars[league_name_clean] = tk.BooleanVar(value=True)

                for team_folder in os.listdir(league_path):
                    team_path = os.path.join(league_path, team_folder)
                    if os.path.isdir(team_path):
                        team_name = team_folder
                        for file in os.listdir(team_path):
                            if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                                full_path = os.path.join(team_path, file)
                                entry = (team_name, full_path)
                                self.leagues_data[league_name_clean].append(entry)
                                self.all_images_master.append(entry)
        
        print(f"Załadowano {len(self.all_images_master)} zdjęć.")

    def create_widgets(self):
        style = ttk.Style()
        style.configure("TButton", font=("Arial", 11), padding=8)

        # Panel górny
        filter_frame = tk.LabelFrame(self.root, text="Ustawienia", font=("Arial", 10), padx=10, pady=5)
        filter_frame.pack(pady=10, fill="x", padx=20)

        self.btn_select_leagues = ttk.Button(filter_frame, text="Zmień ligi", command=self.open_league_window)
        self.btn_select_leagues.pack(side="left", padx=5)

        self.lbl_active_info = tk.Label(filter_frame, text="Wszystkie ligi", font=("Arial", 10, "italic"))
        self.lbl_active_info.pack(side="left", padx=10)

        # Gra
        self.score_label = tk.Label(self.root, text="Wynik: 0/0", font=("Arial", 16, "bold"))
        self.score_label.pack(pady=5)

        self.image_container = tk.Label(self.root, bg="#f0f0f0")
        self.image_container.pack(pady=10)

        lbl_instr = tk.Label(self.root, text="Wpisz nazwę drużyny:", font=("Arial", 12))
        lbl_instr.pack(pady=(5, 2))

        # Live Search
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_listbox)
        self.search_entry = tk.Entry(self.root, textvariable=self.search_var, font=("Arial", 14), width=30)
        self.search_entry.pack(pady=5)
        
        self.search_entry.bind('<Return>', lambda event: self.check_answer())
        self.search_entry.bind('<Down>', self.focus_listbox)

        self.listbox_frame = tk.Frame(self.root)
        self.listbox_frame.pack(pady=5)

        self.results_listbox = tk.Listbox(self.listbox_frame, height=6, width=40, font=("Arial", 12))
        self.results_listbox.pack(side="left", fill="y")
        
        scrollbar = tk.Scrollbar(self.listbox_frame, orient="vertical")
        scrollbar.config(command=self.results_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.results_listbox.config(yscrollcommand=scrollbar.set)

        self.results_listbox.bind('<<ListboxSelect>>', self.fill_entry)
        self.results_listbox.bind('<Return>', self.fill_entry)

        # Przyciski dolne
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)

        self.check_btn = ttk.Button(btn_frame, text="Sprawdź", command=self.check_answer)
        self.check_btn.grid(row=0, column=0, padx=10)

        self.next_btn = ttk.Button(btn_frame, text="Następna >>", command=self.start_new_round, state="disabled")
        self.next_btn.grid(row=0, column=1, padx=10)

        self.result_label = tk.Label(self.root, text="", font=("Arial", 14, "bold"))
        self.result_label.pack(pady=10)

    def open_league_window(self):
        """Otwiera okienko popup z checkboxami - FIX LAYOUT"""
        popup = tk.Toplevel(self.root)
        popup.title("Wybierz ligi")
        popup.geometry("450x600")
        
        # 1. NAJPIERW PAKUJEMY DÓŁ (ŻEBY BYŁ ZAWSZE WIDOCZNY)
        bottom_frame = tk.Frame(popup, padx=10, pady=10, bg="#f0f0f0")
        bottom_frame.pack(side="bottom", fill="x")

        def select_all():
            for var in self.league_vars.values(): var.set(True)
        
        def deselect_all():
            for var in self.league_vars.values(): var.set(False)
        
        def apply_and_close():
            self.apply_league_filter()
            popup.destroy()

        # Przyciski pomocnicze
        helper_frame = tk.Frame(bottom_frame, bg="#f0f0f0")
        helper_frame.pack(side="top", fill="x", pady=(0, 10))
        tk.Button(helper_frame, text="Zaznacz wszystkie", command=select_all).pack(side="left", expand=True)
        tk.Button(helper_frame, text="Odznacz wszystkie", command=deselect_all).pack(side="right", expand=True)

        # Przycisk Zatwierdź
        tk.Button(bottom_frame, text="ZATWIERDŹ", command=apply_and_close, 
                  bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), height=2).pack(side="bottom", fill="x")

        # 2. TERAZ GÓRA I ŚRODEK
        tk.Label(popup, text="Wybierz ligi do gry:", font=("Arial", 12, "bold")).pack(side="top", pady=10)

        list_frame = tk.Frame(popup)
        list_frame.pack(side="top", fill="both", expand=True, padx=10)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        canvas = tk.Canvas(list_frame, yscrollcommand=scrollbar.set)
        scrollbar.config(command=canvas.yview)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        league_names = sorted(list(self.leagues_data.keys()))
        for name in league_names:
            cb = tk.Checkbutton(scrollable_frame, text=name, variable=self.league_vars[name], font=("Arial", 11))
            cb.pack(anchor="w", padx=5, pady=2)

    def apply_league_filter(self, initial=False):
        self.active_images = []
        selected_count = 0

        for league_name, var in self.league_vars.items():
            if var.get():
                self.active_images.extend(self.leagues_data[league_name])
                selected_count += 1

        if selected_count == len(self.leagues_data):
            self.lbl_active_info.config(text="Wszystkie ligi")
        elif selected_count == 0:
             self.lbl_active_info.config(text="BRAK (Zaznacz coś!)")
        else:
             self.lbl_active_info.config(text=f"Wybrano: {selected_count} lig")

        unique_teams = set()
        for team, _ in self.active_images:
            unique_teams.add(team)
        self.active_teams_list = sorted(list(unique_teams))

        if not initial:
            self.score = 0
            self.rounds = 0
            self.score_label.config(text="Wynik: 0/0")
            self.search_var.set("")
            self.update_listbox()
            self.start_new_round()
        else:
            self.start_new_round()

    def update_listbox(self, *args):
        search_term = self.search_var.get()
        self.results_listbox.delete(0, tk.END)

        if search_term == "":
            for item in self.active_teams_list:
                self.results_listbox.insert(tk.END, item)
        else:
            for item in self.active_teams_list:
                if search_term.lower() in item.lower():
                    self.results_listbox.insert(tk.END, item)

    def focus_listbox(self, event):
        self.results_listbox.focus_set()
        if self.results_listbox.size() > 0:
            self.results_listbox.selection_set(0)

    def fill_entry(self, event):
        selection = self.results_listbox.curselection()
        if selection:
            selected_team = self.results_listbox.get(selection[0])
            self.search_var.set(selected_team)
            self.search_entry.focus_set()
            self.search_entry.icursor(tk.END)

    def start_new_round(self):
        self.result_label.config(text="", fg="black")
        self.search_var.set("")
        
        self.check_btn.config(state="normal")
        self.next_btn.config(state="disabled")
        self.search_entry.config(state="normal")
        self.search_entry.focus_set()

        if not self.active_images:
            self.image_container.config(image="", text="Brak wybranych lig.\nKliknij 'Zmień ligi'.", font=("Arial", 14))
            return

        self.current_correct_team, self.current_image_path = random.choice(self.active_images)

        try:
            pil_image = Image.open(self.current_image_path)
            pil_image.thumbnail((400, 400))
            self.tk_image = ImageTk.PhotoImage(pil_image)
            self.image_container.config(image=self.tk_image, text="")
        except Exception as e:
            print(f"Błąd zdjęcia: {e}")
            self.start_new_round()

    def check_answer(self):
        if str(self.check_btn['state']) == 'disabled':
            self.start_new_round()
            return

        user_input = self.search_var.get()
        if not user_input:
            messagebox.showwarning("Błąd", "Wpisz nazwę drużyny!")
            return

        matched_team = None
        for team in self.active_teams_list:
            if user_input.lower() == team.lower():
                matched_team = team
                break
        
        if not matched_team:
            if self.results_listbox.size() == 1:
                matched_team = self.results_listbox.get(0)
                self.search_var.set(matched_team)
            else:
                messagebox.showwarning("Błąd", "Wybierz poprawną nazwę z listy!")
                return

        self.rounds += 1
        
        if matched_team == self.current_correct_team:
            self.score += 1
            self.result_label.config(text=f"BRAWO! To {self.current_correct_team}", fg="green")
        else:
            self.result_label.config(text=f"BŁĄD! To jest: {self.current_correct_team}", fg="red")

        self.score_label.config(text=f"Wynik: {self.score}/{self.rounds}")
        
        self.check_btn.config(state="disabled")
        self.search_entry.config(state="disabled")
        self.next_btn.config(state="normal")
        self.next_btn.focus_set()

if __name__ == "__main__":
    root = tk.Tk()
    app = FootballQuizApp(root)
    root.mainloop()