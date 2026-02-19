import yfinance as yf
from dash import Dash, html, dcc, Input, Output, State, no_update
import plotly.graph_objects as go
from datetime import datetime, timedelta
import google.generativeai as genai
import os
from dash_chat import ChatComponent 

genai.configure(api_key="API_KEY_HERE")  # Replace with your actual API key
model = genai.GenerativeModel('gemini-2.5-flash')
MARKET_SECTORS = {
    'Technology': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'AMD', 'CRM', 'ADBE', 'CSCO', 'INTC', 'ORCL', 'IBM'],
    'Healthcare': ['LLY', 'UNH', 'JNJ', 'MRK', 'ABBV', 'PFE', 'TMO', 'ABT', 'AMGN', 'BMY', 'CVS', 'GILD'],
    'Finance': ['JPM', 'V', 'MA', 'BAC', 'WFC', 'GS', 'MS', 'AXP', 'C', 'BLK', 'SCHW', 'PGR'],
    'Consumer Discretionary': ['AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'SBUX', 'LOW', 'BKNG', 'TJX', 'TGT', 'F', 'MAR']
}

app = Dash(__name__)

# 1. THE UI LAYOUT
app.layout = html.Div(
    style={'fontFamily': 'Arial, sans-serif', 'padding': '30px', 'maxWidth': '1300px', 'margin': '0 auto'},
    children=[
        html.H1("Market Tracker & AI Analyst"),
        html.P("Select a market sector to explore top assets and analyze historical trends."),
        
        # The Control Panel 
        html.Div(
            style={
                'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '10px',
                'border': '1px solid #dee2e6', 'display': 'flex', 'gap': '30px',
                'flexWrap': 'wrap', 'alignItems': 'center', 'marginBottom': '20px'
            },
            children=[
                html.Div([
                    html.Label("1. Choose a Sector:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(id='sector-dropdown', options=[{'label': k, 'value': k} for k in MARKET_SECTORS.keys()], value='Technology', clearable=False, style={'width': '220px', 'marginTop': '5px'})
                ]),
                html.Div([
                    html.Label("2. Select an Asset:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(id='ticker-dropdown', value='AAPL', clearable=False, style={'width': '180px', 'marginTop': '5px'})
                ]),
                # 3. Timeframe Quick-Select Buttons
                html.Div([
                    html.Label("3. Timeframe:", style={'fontWeight': 'bold'}), 
                    html.Br(),
                    dcc.RadioItems(
                        id='timeframe-selector',
                        options=[
                            {'label': ' 1D ', 'value': '1d'},
                            {'label': ' 1W ', 'value': '5d'},
                            {'label': ' 1M ', 'value': '1mo'},
                            {'label': ' 3M ', 'value': '3mo'},
                            {'label': ' 1Y ', 'value': '1y'},
                            {'label': ' 5Y ', 'value': '5y'}
                        ],
                        value='1D', # Default to 1 day
                        inline=True,
                        style={'marginTop': '10px', 'display': 'flex', 'gap': '15px', 'cursor': 'pointer'}
                    )
                ])
            ]
        ),
        
        # SPLIT VIEW: Chart on the left, Chat on the right
        html.Div(
            style={'display': 'flex', 'gap': '20px', 'alignItems': 'flex-start'},
            children=[
                # Chart Area (takes up 65% of the space)
                html.Div(
                    style={'flex': '65', 'minWidth': '0'},
                    children=[
                        dcc.Graph(id='candlestick-chart')
                    ]
                ),
                
                # Chat Area (takes up 35% of the space)
                html.Div(
                    style={
                        'flex': '35', 
                        'height': '450px', 
                        'minWidth': '300px'
                    },
                    children=[
                        ChatComponent(
                            id='ai-chat',
                            messages=[],
                            theme="light",
                            input_placeholder="Ask a question about the stock..."
                        )
                    ]
                )
            ]
        )
    ]
)

# 2. THE UX LOGIC (Callbacks)

# Callback 1: Cascading Dropdown
@app.callback(
    Output('ticker-dropdown', 'options'),
    Output('ticker-dropdown', 'value'),
    Input('sector-dropdown', 'value')
)
def update_tickers(selected_sector):
    tickers = MARKET_SECTORS[selected_sector]
    return tickers, tickers[0]

# Callback 2: Financial Chart Updates with Timeframes
@app.callback(
    Output('candlestick-chart', 'figure'),
    Input('ticker-dropdown', 'value'),
    Input('timeframe-selector', 'value')
)
def update_chart(ticker, timeframe):
    stock = yf.Ticker(ticker)
    
    # UX Logic: If they want 1 Day or 1 Week, we need minute-by-minute data to draw the candles.
    # Otherwise, standard daily data is fine.
    if timeframe == '1d':
        df = stock.history(period='1d', interval='5m')
    elif timeframe == '5d':
        df = stock.history(period='5d', interval='15m')
    else:
        df = stock.history(period=timeframe, interval='1d')
        
    df.reset_index(inplace=True)
    
    # yfinance uses 'Datetime' for intraday and 'Date' for daily data, so we check which one we got
    date_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
    
    fig = go.Figure(data=[go.Candlestick(
        x=df[date_col], 
        open=df['Open'], 
        high=df['High'], 
        low=df['Low'], 
        close=df['Close'], 
        name=ticker
    )])
    
    # We turn off the rangeslider because our new buttons do the job better!
    fig.update_layout(
        title=f"{ticker} Market Performance", 
        yaxis_title="Price (USD)",
        plot_bgcolor='white', 
        paper_bgcolor='#f8f9fa',
        margin=dict(l=40, r=20, t=40, b=20), 
        xaxis_rangeslider_visible=False
    )
    
    # This automatically removes empty gaps in the chart when the market is closed on weekends
    if timeframe not in ['1y', '5y']:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
        
    return fig

# Callback 3: The REAL (and safe!) Chatbot Logic
@app.callback(
    Output('ai-chat', 'messages'),
    Input('ai-chat', 'new_message'),
    State('ai-chat', 'messages'),
    State('ticker-dropdown', 'value')
)
def update_chat(new_message, messages, active_ticker):
    if not new_message:
        if not messages:
            return [{"role": "assistant", "content": "Hello! I am your AI Market Analyst. Ask me anything about this stock!"}]
        return no_update
        
    # FIX: Make a copy of the list so we don't permanently corrupt the layout memory!
    updated_messages = messages.copy()
    
    # 1. Append the user's message to our copied list
    updated_messages.append(new_message)
    user_text = new_message.get('content', '')
    
    try:
        # 2. Fetch live context from Yahoo Finance
        stock = yf.Ticker(active_ticker)
        info = stock.info.get('longBusinessSummary', 'No company summary available.')
        recent_news = stock.news[:3] if stock.news else []
        news_text = "\n".join([f"- {n.get('title', 'News')}" for n in recent_news]) if recent_news else "No recent news."
        
        # 3. Create the prompt for the LLM
        prompt = f"""
        You are a professional, helpful financial AI assistant built into a stock market dashboard.
        The user is currently looking at the stock ticker: {active_ticker}.
        
        Here is the live background context for {active_ticker}:
        {info}
        
        Here are the latest news headlines for {active_ticker}:
        {news_text}
        
        User's Question: {user_text}
        
        Please answer the user's question concisely and accurately based on this context. 
        Keep it conversational, professional, and directly address their query.
        """
        
        # 4. Generate the response from Gemini
        response = model.generate_content(prompt)
        bot_reply = response.text
        
    except Exception as e:
        bot_reply = f"Sorry, I ran into a backend error: {str(e)}"
    
    # 5. Append AI's reply to our copied list
    updated_messages.append({"role": "assistant", "content": bot_reply})
    
    # 6. Return the clean, copied list to the UI
    return updated_messages

if __name__ == '__main__':
    app.run(debug=True)
