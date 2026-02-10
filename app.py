import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import os

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Solar Tracker Analytics",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- HELPER FUNCTIONS ---
@st.cache_data
def load_data(file_path):
    """
    Loads CSV data and normalizes column names based on your Simulink output.
    """
    if not os.path.exists(file_path):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(file_path)

        # Normalize column names    
        # ['time', 'Pl/t', 'Ppv/t', 'Pload', 'Ppv', 'Vload:1', 'Vpv', 'Iload', 'Ipv']
        rename_map = {
            "time": "Time",
            "Time_Seconds": "Time",  # Handle input data format
            "Pl/t": "Energy_Load",   
            "Ppv/t": "Energy_PV",    
            "Vload:1": "Vload"       
        }
        df.rename(columns=rename_map, inplace=True)
        
        # Convert Time to Hours
        if "Time" in df.columns:
            df["Time"] = df["Time"] / 3600.0
            
        return df
    except Exception as e:
        st.error(f"Error loading {file_path}: {e}")
        return pd.DataFrame()



# Map your files exactly as requested
file_map = {
    "Clear Day": {
        "Tracking": "./Data/clear_0.csv",
        "Fixed": "./Data/clear_1_fix_33.csv"
    },
    "Cloudy Day": {
        "Tracking": "./Data/cloudy_0.csv",
        "Fixed": "./Data/cloudy_1.csv"
    }
}
file_map_input = {
    "Clear Day": "./Data/phoenix_clear_1s.csv",
    "Cloudy Day": "./Data/phoenix_cloudy_1s.csv"
}

# --- MAIN APP ---
st.title("Solar Tracker & MPPT Performance Analysis")

# 1. MODEL ARCHITECTURE SECTION
with st.expander("Simulink Model", expanded=True):
    st.write("""
    **System Topology:**
    * **Source:** NREL Solar Data for coordinates near Phoenix, AZ
    * **MPPT:** Perturb & Observe (P&O) Algorithm controlling a Boost Converter
    * **Tracking Logic:** Hybrid approach (switching between Astronomical Tracking and Flat stow)
    """)
    
    # Updated path for the screenshot
    img_path = "./Data/MODEL.png"
    if os.path.exists(img_path):
        image = Image.open(img_path) 
        st.image(image, caption="Simulink Model: Tracker Logic & Power Electronics", width="stretch")
    else:
        st.warning(f" Image not found at {img_path}. Please check the filename.")

# --- CONFIGURATION ---
selected_day = st.segmented_control(
    "Weather Scenario", 
    ["Clear Day", "Cloudy Day"], 
    default="Clear Day"
)

# Load Data based on selection
paths = file_map[selected_day]
df_track = load_data(paths["Tracking"])
df_fixed = load_data(paths["Fixed"])

# Load separate input data for Tab 0 (Input Data Details)
# Load separate input data for Tab 0 (Input Data Details)
df_input = load_data(file_map_input[selected_day])

# Only proceed if data loaded successfully
if not df_track.empty and not df_fixed.empty:
    
    # --- METRICS ROW ---
    # We take the maximum value of the integrated energy column for Total Energy
    # (Since it accumulates over time, max value = total energy)
    total_e_track = df_track["Energy_Load"].max()
    total_e_fixed = df_fixed["Energy_Load"].max()
    
    # Calculate Gain
    if total_e_fixed > 0:
        gain_pct = ((total_e_track - total_e_fixed) / total_e_fixed) * 100
    else:
        gain_pct = 0
    
    # Create 3 columns for metrics
    m1, m2, m3 = st.columns(3)
    m1.metric(label="Total Energy (Tracking)", value=f"{total_e_track:.2f} Wh")
    m2.metric(label="Total Energy (Fixed 33°)", value=f"{total_e_fixed:.2f} Wh")
    m3.metric(label="Efficiency Gain", value=f"{gain_pct:.2f}%", delta=f"{gain_pct:.2f}%")
    
    st.divider()

    # --- TABS FOR ANALYSIS ---
    tab0, tab1, tab2, tab3 = st.tabs(["Input Data", "Power & Energy", "Converter Losses", "MPPT Diagnostics"])

    # TAB 0: Input Data Details
    with tab0:
        st.subheader("Input Weather Data")
        
        # Check if we have the necessary columns (from Input Data CSVs)
        # We'll prioritize the 'Tracking' dataframe as the source for weather data 
        # (assuming both Tracking/Fixed input files have same weather data)
        # Check if we have the necessary columns (from Input Data CSVs)
        # Check if we have the necessary columns (from Input Data CSVs)
        # We use df_input which is specifically loaded from file_map_input
        if not df_input.empty and "Temperature" in df_input.columns and "GHI" in df_input.columns:
            col_temp, col_irr = st.columns(2)
                
            with col_temp:
                # Graph 1: Temperature
                fig_temp = px.line(df_input, x="Time", y="Temperature", title="Ambient Temperature (°C)")
                fig_temp.update_layout(xaxis_title="Time (h)", yaxis_title="Temperature (°C)")
                st.plotly_chart(fig_temp, use_container_width=True)
                
            with col_irr:
                # Graph 2: Irradiance
                fig_irr = go.Figure()
                fig_irr.add_trace(go.Scatter(x=df_input["Time"], y=df_input["GHI"], name="GHI", line=dict(color="#FFC107")))
                fig_irr.add_trace(go.Scatter(x=df_input["Time"], y=df_input["DNI"], name="DNI", line=dict(color="#FF5722")))
                fig_irr.add_trace(go.Scatter(x=df_input["Time"], y=df_input["DHI"], name="DHI", line=dict(color="#03A9F4")))
                fig_irr.update_layout(
                    title="Solar Irradiance (W/m²)", 
                    xaxis_title="Time (h)", 
                    yaxis_title="Irradiance (W/m²)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_irr, use_container_width=True)
        else:
            st.info("Weather data (Temperature, GHI) not available or input data file not found.")
            

    # TAB 1: POWER & ENERGY COMPARISON
    with tab1:
        st.subheader("Tracking vs. Fixed Performance")
        
        col1, col2 = st.columns(2)
        with col1:
            # Graph 1: Instantaneous Power Comparison
            fig_pwr = go.Figure()
            fig_pwr.add_trace(go.Scatter(x=df_track["Time"], y=df_track["Pload"], name="Tracking Output", line=dict(color="#00CC96")))
            fig_pwr.add_trace(go.Scatter(x=df_fixed["Time"], y=df_fixed["Pload"], name="Fixed Output", line=dict(color="#EF553B", dash='dash')))
            fig_pwr.update_layout(
                title="Instantaneous Power Output at Load", 
                xaxis_title="Time (h)", 
                yaxis_title="Power (W)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_pwr, use_container_width=True)

        with col2:
            # Graph 2: Cumulative Energy
            fig_cum = go.Figure()
            fig_cum.add_trace(go.Scatter(x=df_track["Time"], y=df_track["Energy_Load"], name="Tracking Energy", line=dict(color="#00CC96")))
            fig_cum.add_trace(go.Scatter(x=df_fixed["Time"], y=df_fixed["Energy_Load"], name="Fixed Energy", line=dict(color="#EF553B")))
            fig_cum.update_layout(
                title="Cumulative Energy Harvest", 
                xaxis_title="Time (h)", 
                yaxis_title="Energy (Wh)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_cum, use_container_width=True)

    # TAB 2: Convertor Losses
    with tab2:
        st.subheader("Electrical    Losses due to Convertor")
        col_a, col_b = st.columns(2)
        
        with col_a:
            # Graph 3: Source vs Load (Shows Converter Loss)
            fig_loss = go.Figure()
            fig_loss.add_trace(go.Scatter(x=df_track["Time"], y=df_track["Ppv"], name="Panel Power (Input)"))
            fig_loss.add_trace(go.Scatter(x=df_track["Time"], y=df_track["Pload"], name="Load Power (Output)"))
            fig_loss.update_layout(title="Power Conversion: Input vs Output", xaxis_title="Time (h)", yaxis_title="Power (W)")
            st.plotly_chart(fig_loss, use_container_width=True)

        with col_b:
            # Graph 4: Instantaneous Efficiency
            # Filter out low power noise (e.g., night time or < 1W) to avoid division by zero spikes
            mask = df_track["Ppv"] > 1.0
            df_eff = df_track[mask].copy()
            df_eff["Efficiency"] = (df_eff["Pload"] / df_eff["Ppv"]) * 100
            
            fig_eff = px.line(df_eff, x="Time", y="Efficiency", title="Converter Efficiency (%)")
            fig_eff.update_yaxes(range=[90, 100]) # Focus on the relevant efficiency range
            st.plotly_chart(fig_eff, use_container_width=True)

    # TAB 3: MPPT BEHAVIOR
    with tab3:
        st.subheader("MPPT Operating Point Analysis")
        
        # Graph 5: IV Curve Scatter
        # Shows where the MPPT "hunted" for power
        fig_iv = px.scatter(
            df_track, 
            x="Vpv", 
            y="Ipv", 
            color="Ppv", 
            title="MPPT Trajectory at Pannel (VvsI)",
            labels={"Vpv": "Panel Voltage (V)", "Ipv": "Panel Current (A)", "Ppv": "Power (W)"},
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_iv, use_container_width=True)

        fig_v = px.scatter(
            df_track, 
            x="Vload", 
            y="Iload", 
            color="Pload", 
            title="MPPT Trajectory at Load (VvsI)",
            labels={"Vload": "Load Voltage (V)", "Iload": "Load Current (A)", "Pload": "Load Power (W)"},
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig_v, use_container_width=True)

else:
    st.error("Data could not be loaded. Please ensure the 'Data/extracted_csvs' folder exists and contains the CSV files.")