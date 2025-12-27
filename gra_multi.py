import streamlit as st
import os
import random
import time
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

# --- CACHOWANIE DANYCH (Szybsze ładowanie) ---
@st.cache_data
def load_csv_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return None

# ==============================================================================
# 2. ZARZĄDZANIE POKOJAMI (Zoptymalizowane)
# ==============================================================================

class GameState:
    def __init__(self, room_id):
        self.room_id = room_id
        self.created_at = time.time()
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        self.last_activity = time.time() # Do usuwania nieaktywnych pokoi
        
        self.mode = "multi"
        self.p1_name = None; self.p2_name = None
        self.p1_score = 0; self.p2_score = 0
        self.status = "lobby"
        self.current_team = None; self.current_image = None
        self.image_pool = []; self.round_id = 0; self.input_reset_counter = 0
        self.current_round_starter = "P1"; self.who_starts_next = "P1"
        self.p1_locked = False; self.p2_locked = False
        self.winner_last_round = None; self.last_correct_answer = ""
        self.disconnect_reason = ""
        self.active_category_name = "👕 Koszulki (Ligi)"

class RoomManager:
    def __init__(self):
        self.rooms = {} 

    def get_room(self, room_id):
        self.cleanup_rooms()
        if room_id not in self.rooms:
            self.rooms[room_id] = GameState(room_id)
        return self.rooms[room_id]

    def cleanup_rooms(self):
        now = time.time()
        # Pokój usuwamy tylko, jeśli nikt w nim nie był przez 10 minut
        # lub jeśli nikt nie wszedł przez 5 minut od założenia
        timeout_inactive = 600.0 
        to_delete = [rid for rid, r in self.rooms.items() if now - r.last_activity > timeout_inactive]
        for rid in to_delete: del self.rooms[rid]

@st.cache_resource
def get_manager(): return RoomManager()
manager = get_manager()

# ==============================================================================
# 3. LOGIKA I WIDOKI (Zmiany w ładowaniu i UX)
# ==============================================================================

def load_images_filtered(server, csv_path, selected_leagues, use_top_20_filter=False):
    server.image_pool = []
    df = load_csv_data(csv_path)
    if df is None: return

    try:
        temp_df = df.copy()
        if selected_leagues: 
            temp_df = temp_df[temp_df['Liga'].isin(selected_leagues)]
        
        # Filtr Top 20
        if use_top_20_filter:
            # Lista klubów zdefiniowana globalnie (TOP_20_CLUBS)
            col = next((c for c in ['Klub_Filter', 'Klub', 'Odpowiedz'] if c in temp_df.columns), None)
            if col: temp_df = temp_df[temp_df[col].isin(TOP_20_CLUBS)]
        
        ans_col = 'Odpowiedz' if 'Odpowiedz' in temp_df.columns else 'Klub'
        for _, row in temp_df.iterrows():
            server.image_pool.append((row[ans_col], row['Link_Bezposredni']))
    except Exception as e: st.error(f"Błąd danych: {e}")

# ... (Reszta funkcji start_new_round, handle_guess itd. pozostaje bez zmian)

def view_main_menu():
    st.markdown("<h1 style='text-align: center;'>⚽ FOOTBALL QUIZ</h1>", unsafe_allow_html=True)
    
    with st.container(border=True):
        room_input = st.text_input("Nazwa pokoju (stolika):", placeholder="np. Mecz_Finałowy", key="room_input")
        if st.button("WEJDŹ DO POKOJU 🚪", type="primary", use_container_width=True):
            if room_input:
                st.session_state.current_room_id = room_input.strip()
                st.rerun()
            else: st.warning("Wpisz nazwę pokoju!")

    manager.cleanup_rooms()
    active = list(manager.rooms.keys())
    if active:
        st.write("### 🟢 Aktywne stoliki:")
        cols = st.columns(3)
        for i, rid in enumerate(active):
            with cols[i % 3]:
                if st.button(f"Stolik: {rid}", key=f"btn_{rid}"):
                    st.session_state.current_room_id = rid
                    st.rerun()

# ==============================================================================
# 4. GŁÓWNA PĘTLA Z OBSŁUGĄ BŁĘDÓW
# ==============================================================================

def main():
    if 'current_room_id' not in st.session_state:
        view_main_menu()
    else:
        room_id = st.session_state.current_room_id
        server = manager.get_room(room_id)
        
        # Heartbeat i bezpieczeństwo sesji
        if 'my_role' not in st.session_state: 
            st.session_state.my_role = None
        
        # Aktualizujemy czas aktywności pokoju
        server.last_activity = time.time()
        
        if st.session_state.my_role:
            if st.session_state.my_role == "P1": server.p1_last_seen = time.time()
            else: server.p2_last_seen = time.time()

        # Sprawdzanie walkowera (tylko w trakcie gry)
        if server.status in ["playing", "round_over"] and server.mode == "multi":
            now = time.time()
            limit = 15.0
            if now - server.p1_last_seen > limit:
                server.status = "disconnected"; server.disconnect_reason = f"Gracz {server.p1_name} zniknął!"
            elif now - server.p2_last_seen > limit:
                server.status = "disconnected"; server.disconnect_reason = f"Gracz {server.p2_name} zniknął!"

        # Renderowanie widoków
        if server.status == "lobby": view_game_lobby(server)
        elif server.status == "playing": view_playing(server)
        elif server.status == "round_over": view_round_over(server)
        elif server.status == "finished": view_finished(server)
        elif server.status == "disconnected": view_disconnected(server)

if __name__ == "__main__":
    main()















