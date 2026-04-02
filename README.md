cat <<EOF > README.md
# myShortermAnalyser 📈

An automated Python-based Telegram bot designed for **Short-Term (Swing) and Intraday (MIS)** stock analysis in the Indian Market.

## 🚀 Features
- **Short-Term Strategy**: Identifies stocks touching the 20-day EMA with bullish volume.
- **Intraday (MIS) Analysis**: Scans for Open=High/Low and VWAP breakouts.
- **Automated Scheduling**: Runs analysis at market open and close.
- **Telegram Integration**: Sends real-time alerts and reports directly to your phone.

## 📦 Setup & Installation
1. **Clone & Install**:
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`
2. **Environment Variables**:
   Set your \`TELEGRAM_BOT_TOKEN\` and \`GROQ_API_KEY\` in your environment.
3. **Run**:
   \`\`\`bash
   python main.py
   \`\`\`

## 📜 Disclaimer
This tool is for educational purposes only. Trading stocks involves risk.
EOF



To run the Nifty 50 analysis, use this command in your terminal:

   python3 main.py --stocktips nifty50

  How to run it:
   1. Open your terminal.
   2. Navigate to your project folder:
   1     cd "/Users/nathiya/Documents/my app/newstockbot"
   3. Run the command:
       python3 main.py --stocktips nifty50
