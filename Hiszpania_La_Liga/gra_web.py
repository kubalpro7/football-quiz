import streamlit as st
import os
import random
from PIL import Image

# --- KONFIGURACJA ---
FOLDER_Z_KOSZULKAMI = "MEGA_KOLEKCJA_25_26_CENZURA"

# --- FUNKCJE POMOCNICZE ---
@st.cache_data # To sprawia, że dane ładują się tylko raz (szybciej)
def load_data():
    """Skanuje foldery i zwraca strukturę danych."""
    if not os.path.exists(FOLDER_Z_KOSZULKAMI):
        return {}, []

    leagues_data = {}
    all_images = []

    for league_folder in os.listdir(FOLDER_Z_KOSZULKAMI):
        league_path = os.path.join(FOLDER_Z_KOSZULKAMI, league_folder)
        if os.path.isdir(league_path):
            clean_name = league_folder.replace("_", " ")
            leagues_data[clean_name] = []
            
            for team_folder in os.listdir(league_path):
                team_path = os.path.join(league_path, team_folder)
                if os.path.isdir(team_path):
                    for file in os.listdir(team_path):
                        if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                            full_path = os.path.join(team_path, file)
                            entry = (team_folder, full_path)
                            leagues_data[clean_name].append(entry)
                            all_images.append(entry)
    
    return leagues_data, all_images

# --- INICJALIZACJA STANU GRY ---
# Streamlit odświeża kod przy każdym kliknięciu, więc musimy zapamiętać stan w session_state
if 'score' not in st.session_state:
    st.session_state.score = 0
if 'rounds' not in st.session_state:
    st.session_state.rounds = 0
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'current_team' not in st.session_state:
    st.session_state.current_team = None
if 'game_over' not in st.session_state:
    st.session_state.game_over = False
if 'message' not in st.session_state:
    st.session_state.message = ""
if 'message_color' not in st.session_state:
    st.session_state.message_color = "black"

# Ładowanie danych
leagues_map, all_images_list = load_data()

# --- INTERFEJS BOCZNY (Filtrowanie) ---
st.sidebar.header("⚙️ Ustawienia")
league_options = sorted(list(leagues_map.keys()))
selected_leagues = st.sidebar.multiselect(
    "Wybierz ligi:", 
    league_options, 
    default=league_options
)

# Budowanie aktywnej puli zdjęć
active_pool = []
for league in selected_leagues:
    active_pool.extend(leagues_map[league])

# Lista unikalnych drużyn do wyboru (dla selectboxa)
active_teams_list = sorted(list(set([img[0] for img in active_pool])))

# --- FUNKCJE LOGIKI ---
def next_round():
    if not active_pool:
        return
    
    # Losowanie
    team, img_path = random.choice(active_pool)
    st.session_state.current_team = team
    st.session_state.current_image = img_path
    st.session_state.game_over = False
    st.session_state.message = ""

def check_answer():
    user_choice = st.session_state.user_input
    
    if not user_choice:
        return

    st.session_state.rounds += 1
    
    if user_choice == st.session_state.current_team:
        st.session_state.score += 1
        st.session_state.message = f"BRAWO! To jest {st.session_state.current_team} ✅"
        st.session_state.message_color = "green"
    else:
        st.session_state.message = f"BŁĄD! To był: {st.session_state.current_team} ❌"
        st.session_state.message_color = "red"
    
    st.session_state.game_over = True

# Start pierwszej rundy, jeśli nic nie ma
if st.session_state.current_image is None and active_pool:
    next_round()

# --- GŁÓWNY INTERFEJS ---
st.title("⚽ Quiz Koszulkowy 2025/26")

# Wyświetlanie wyniku
col1, col2 = st.columns(2)
col1.metric("Punkty", st.session_state.score)
col2.metric("Rundy", st.session_state.rounds)

if not active_pool:
    st.error("Brak zdjęć! Zaznacz przynajmniej jedną ligę w panelu bocznym.")
else:
    # Wyświetlanie zdjęcia
    if st.session_state.current_image:
        image = Image.open(st.session_state.current_image)
        st.image(image, use_container_width=True)

    # Mechanika gry
    if not st.session_state.game_over:
        # Formularz wyboru (Searchable Selectbox - działa jak Live Search!)
        st.selectbox(
            "Jaka to drużyna?", 
            options=[""] + active_teams_list, # Pusta opcja na start
            key="user_input",
            placeholder="Wpisz lub wybierz..."
        )
        
        if st.button("Sprawdź", type="primary"):
            if st.session_state.user_input:
                check_answer()
                st.rerun() # Odśwież stronę, żeby pokazać wynik
            else:
                st.warning("Wybierz drużynę z listy!")
    else:
        # Ekran po odpowiedzi
        if st.session_state.message_color == "green":
            st.success(st.session_state.message)
        else:
            st.error(st.session_state.message)
        
        if st.button("Następna koszulka ➡️"):
            next_round()
            st.rerun()