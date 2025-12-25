import streamlit as st
import os
import random
import time
import difflib
from PIL import Image

# ==============================================================================
# 1. KONFIGURACJA
# ==============================================================================
st.set_page_config(page_title="Football Quiz V11", layout="centered", page_icon="⚽")

# CSS - Czysty wygląd
st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 5rem !important; max-width: 800px; }
    .stApp { background-color: #0e1117; }
    #MainMenu, footer, header {visibility: hidden;}
    
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
    }
    img { max-height: 400px !important; object-fit: contain; border-radius: 12px; margin-bottom: 10px; }
    .player-box { text-align: center; padding: 10px; border-radius: 8px; width: 100%; font-weight: bold; }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; }
    .p2-box { background-color: #0d47a1; color: #90caf9; }
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    
    /* Wymuszenie układu przycisków w jednej linii */
    div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
    button { height: 50px !important; width: 100% !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. STAN SERWERA
# ==============================================================================
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby" 
        self.current_team = None
        self.current_image = None
        self.image_pool = []
        self.round_id = 0
        self.input_reset_counter = 0 
        self.current_round_starter = "P1" 
        self.p1_locked = False
        self.p2_locked = False
        self.who_starts_next = "P1"
        self.winner_last_round = None
        self.last_correct_answer = ""
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        self.disconnect_reason = ""

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# ==============================================================================
# 3. LOGIKA
# ==============================================================================
def update_heartbeat(role):
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()

def check_disconnections():
    if server.status not in ["playing", "round_over"]: return
    # Timeout 15 sekund
    if time.time() - server.p1_last_seen > 15.0:
        server.status = "disconnected"; server.disconnect_reason = f"{server.p1_name} uciekł!"
    elif time.time() - server.p2_last_seen > 15.0:
        server.status = "disconnected"; server.disconnect_reason = f"{server.p2_name} uciekł!"

def get_leagues(folder):
    if not os.path.exists(folder): return []
    return sorted([d.replace("_", " ") for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d)) and not d.startswith(".")])

def load_images(folder, selected):
    server.image_pool = []
    if not os.path.exists(folder): return
    for root, dirs, files in os.walk(folder):
        path_parts = root.split(os.sep)
        if any(part.replace("_", " ") in selected for part in path_parts):
            for f in files:
                if f.lower().endswith(('.jpg','.png','.jpeg')):
                    team = os.path.basename(root).replace("_", " ")
                    if team not in [".", folder]:
                        server.image_pool.append((team, os.path.join(root, f)))

def start_round():
    if not server.image_pool: return
    t, i = random.choice(server.image_pool)
    server.current_team = t
    server.current_image = i
    server.p1_locked = False
    server.p2_locked = False
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1
    server.input_reset_counter = 0
    server.current_round_starter = server.who_starts_next

def reset_all():
    server.__init__() 
    st.rerun()

FOLDER = "."

# ==============================================================================
# 4. WIDOKI (Renderowane wewnątrz Main Placeholder)
# ==============================================================================

def render_lobby():
    st.markdown("<h1 style='text-align: center;'>🏆 LOBBY</h1>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name: st.success(f"✅ {server.p1_name}")
        else:
            n1 = st.text_input("Nick P1", key="n1")
            if st.button("Zajmij P1"):
                server.p1_name = n1; st.session_state.my_role = "P1"; update_heartbeat("P1"); st.rerun()
    with c2:
        st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
        if server.p2_name: st.success(f"✅ {server.p2_name}")
        else:
            n2 = st.text_input("Nick P2", key="n2")
            if st.button("Zajmij P2"):
                server.p2_name = n2; st.session_state.my_role = "P2"; update_heartbeat("P2"); st.rerun()

    st.divider()

    # WYBÓR LIG - Tylko tutaj!
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia")
        leagues = get_leagues(FOLDER)
        sel = st.multiselect("Wybierz ligi:", leagues, default=leagues)
        
        st.write("")
        if server.p1_name and server.p2_name:
            if st.button("START MECZU 🚀", type="primary"):
                if not sel: st.error("Wybierz ligę!")
                else:
                    load_images(FOLDER, sel)
                    if not server.image_pool: st.error("Brak zdjęć!")
                    else:
                        start_round()
                        st.rerun()
        else:
            st.warning("Czekamy na drugiego gracza...")
            time.sleep(1); st.rerun()
    elif st.session_state.my_role == "P2":
        st.info("Czekamy na start..."); time.sleep(1); st.rerun()
    else:
        time.sleep(1); st.rerun()

def render_playing():
    # Wynik
    st.markdown(f"""<div class="score-board">
        <span style="color:#66bb6a">{server.p1_name}: {server.p1_score}</span>
        <span>VS</span>
        <span style="color:#42a5f5">{server.p2_name}: {server.p2_score}</span>
    </div>""", unsafe_allow_html=True)

    # Info tury
    if server.p1_locked: st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} zablokowany!</div>", unsafe_allow_html=True)
    if server.p2_locked: st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} zablokowany!</div>", unsafe_allow_html=True)

    # Zdjęcie
    if server.current_image:
        try: st.image(Image.open(server.current_image), use_container_width=True)
        except: st.error("Błąd pliku")

    # Tryb wpisywania
    c_tog, _ = st.columns([1,2])
    with c_tog:
        mode = st.toggle("Klawiatura (Enter)", value=st.session_state.input_mode)
        if mode != st.session_state.input_mode: st.session_state.input_mode = mode; st.rerun()

    # FORMULARZ
    teams = sorted(list(set([x[0] for x in server.image_pool])))
    with st.form(key=f"gf_{server.round_id}_{server.input_reset_counter}"):
        guess = ""
        if st.session_state.input_mode:
            guess = st.text_input("Klub:", placeholder="Wpisz i Enter")
        else:
            guess = st.selectbox("Klub:", [""] + teams)
        
        st.write("")
        
        # Przyciski w jednej linii (układ 3, 1, 1)
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: sub_guess = st.form_submit_button("ZGŁASZAM 🎯", type="primary")
        with c2: sub_surr = st.form_submit_button("🏳️", help="Poddaję")
        with c3:
            if st.session_state.my_role == "P1": sub_end = st.form_submit_button("🏁", type="secondary", help="Zakończ Grę")
            else: sub_end = False

    # Logika akcji
    role = st.session_state.my_role
    
    if sub_end and role == "P1":
        server.status = "finished"; st.rerun()

    if sub_guess and guess:
        locked = server.p1_locked if role == "P1" else server.p2_locked
        if not locked:
            match = False
            if guess == server.current_team: match = True
            else:
                sims = difflib.get_close_matches(guess, teams, n=1, cutoff=0.5)
                if sims and sims[0] == server.current_team: match = True
            
            if match:
                if role == "P1": server.p1_score += 1; server.who_starts_next = "P2"
                else: server.p2_score += 1; server.who_starts_next = "P1"
                server.winner_last_round = role; server.last_correct_answer = server.current_team
                server.status = "round_over"; st.rerun()
            else:
                st.toast("ŹLE!", icon="❌")
                server.input_reset_counter += 1
                if role == "P1": server.p1_locked = True; server.p2_locked = False
                else: server.p2_locked = True; server.p1_locked = False
                st.rerun()
        else:
            st.toast("Jesteś zablokowany!", icon="⛔")

    if sub_surr:
        server.input_reset_counter += 1
        if role == "P1": server.p1_locked = True
        else: server.p2_locked = True
        st.rerun()

    # Obaj zablokowani
    if server.p1_locked and server.p2_locked:
        server.winner_last_round = "NIKT"
        server.last_correct_answer = server.current_team
        server.who_starts_next = "P2" if server.current_round_starter == "P1" else "P1"
        server.status = "round_over"
        st.rerun()

    time.sleep(1); st.rerun()

def render_round_over():
    if st.session_state.my_role == "P1":
        if st.sidebar.button("🏁 ZAKOŃCZ GRĘ"): server.status = "finished"; st.rerun()

    win = server.winner_last_round
    if win == "P1": bg="#1b5e20"; txt=f"Punkt: {server.p1_name}"
    elif win == "P2": bg="#0d47a1"; txt=f"Punkt: {server.p2_name}"
    else: bg="#555"; txt="Nikt nie zgadł"

    st.markdown(f"<div style='background:{bg}; color:white; padding:15px; border-radius:10px; text-align:center;'><h2>{txt}</h2></div>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center; color:#4CAF50;'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    if server.current_image: st.image(Image.open(server.current_image), use_container_width=True)

    st.divider()
    
    act = server.who_starts_next
    if st.session_state.my_role == act:
        st.success("Twoja kolej!")
        if st.button("NASTĘPNA RUNDA ➡️", type="primary"):
            start_round(); st.rerun()
    else:
        st.info(f"Czekaj na {act}..."); time.sleep(1); st.rerun()

def render_finished():
    st.markdown("<h1 style='text-align:center'>KONIEC MECZU</h1>", unsafe_allow_html=True)
    st.markdown(f"<h2 style='text-align:center'>{server.p1_score} - {server.p2_score}</h2>", unsafe_allow_html=True)
    if st.button("REWANŻ 🔄", type="primary"): reset_all()

def render_disconnected():
    st.error(f"WALKOWER! {server.disconnect_reason}")
    if st.button("RESET"): reset_all()

# ==============================================================================
# 5. MAIN (KONTENER - GWARANCJA CZYSTOŚCI)
# ==============================================================================
def main():
    if 'my_role' not in st.session_state: st.session_state.my_role = None
    if 'input_mode' not in st.session_state: st.session_state.input_mode = True

    # Pasek boczny DEBUG
    st.sidebar.title("WERSJA V11 (PANCERNA)")
    st.sidebar.caption(f"Status: {server.status}") # To pokaże Ci w jakim stanie jest gra
    if st.sidebar.button("HARD RESET"): reset_all()

    if st.session_state.my_role: update_heartbeat(st.session_state.my_role)
    check_disconnections()

    # --- GLÓWNY KONTENER (PLACEHOLDER) ---
    # To jest klucz do naprawy. Tworzymy puste "pudełko" na całą stronę.
    # Wszystko co rysujemy, trafia DO ŚRODKA.
    # Jeśli w pliku są jakieś śmieci na dole, będą POZA tym pudełkiem, ale 
    # logika gry ich nie dotknie.
    
    main_container = st.empty()
    
    with main_container.container():
        if server.status == "lobby": render_lobby()
        elif server.status == "playing": render_playing()
        elif server.status == "round_over": render_round_over()
        elif server.status == "finished": render_finished()
        elif server.status == "disconnected": render_disconnected()

if __name__ == "__main__":
    main()
