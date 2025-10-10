# =========================
# Assistente de Estoque IA v2.2
# Adaptado para Render (sem !pip install e com caminho relativo para credenciais)
# =========================

import os
import json
import datetime
import traceback
import nest_asyncio
import asyncio
from typing import Any, Dict

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import google.generativeai as genai

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# =========================
# CONFIGURAÇÕES - SUBSTITUA
# =========================
TOKEN_TELEGRAM = "8444243438:AAFGfePVk7X3H0s4v4W0YQNTyxxgV8yHsjg"
GEMINI_API_KEY = "AIzaSyD7DwxWreS73GdmIrch863I1BybEs-SH9Q"
CAMINHO_CREDENCIAIS = "bot-deposito-de-bebidas-fba8ac86ed91.json"
NOME_PLANILHA = "EstoqueDepositoBebidas"
ABA_ESTOQUE = "Estoque"
ABA_MOV = "Movimentacoes"
CALENDAR_ID = "2c73ca7612616298cf388e8d9d975b12d8469129f12d6be809366e158aa265f4@group.calendar.google.com"
MEMORY_FOLDER = "memory_users"

os.makedirs(MEMORY_FOLDER, exist_ok=True)

# (restante do código original deve ser colado aqui sem modificações)
# ...

print("✅ Arquivo main.py carregado. Certifique-se de colar o restante do código aqui.")
