import asyncio
import logging
import pathlib
import json
from datetime import date, timedelta

import aiohttp
import websockets
import names
from websockets import WebSocketServerProtocol, WebSocketProtocolError
from websockets.exceptions import ConnectionClosedOK

logging.basicConfig(level=logging.INFO)
BASE_DIR = pathlib.Path()

async def request(param_list):
    async with aiohttp.ClientSession() as session:    
        for param in param_list:  
            try:           
                async with session.get("https://api.privatbank.ua/p24api/exchange_rates?", params = param) as response:
                    if response.status == 200:
                        result = await response.json()
                        output_data(result)
                    else: 
                        logging.error(f"Error status: {response.status}")
            except aiohttp.ClientConnectorError as err: 
                logging.error(f"Connection error: {err}")
    return None
    
def find_currency(requested_currency: str, answer: dict) -> dict: #знайти валюту в даних від приватбанку
    i = 0
    length_exchangeRate = len(answer.get("exchangeRate"))
    while answer.get("exchangeRate")[i].get("currency") != requested_currency:
        i += 1
        if i == length_exchangeRate:
            print("Requested currency is not correct")
            return None
            
    requested_currency_Rate = answer.get("exchangeRate")[i]       
    return requested_currency_Rate, answer.get("date")    
    
#формується параметр дати для запиту данних в API
#param = {"date": "10.02.2023"}   - приклад необхідного формату (на поточну дату відповідь сервера - 500???)
async def date_param(quantity_days): 
    quantity_days = int(quantity_days)
    today = date.today()
    param_list = []
    while quantity_days != 0:
        days = quantity_days
        pre_day = (today - timedelta(days)).strftime("%d.%m.%Y")
        quantity_days -= 1 
        param = {"date": pre_day}   
        param_list.append(param) 
    await request(param_list)
    return None

def read_json_file(): #читання даних з файла json
    with open(BASE_DIR.joinpath("storage/data.json"), 'r', encoding='utf-8') as fd:
        text = fd.readline()
        if text:
            upload = json.loads(text)  
    return upload

def write_json_file(output): #запис даних до файла json 
    upload = read_json_file()         
    with open(BASE_DIR.joinpath("storage/data.json"), 'w', encoding='utf-8') as fd:                
        upload.append(output)
        json.dump(upload, fd, ensure_ascii=False)

def output_data(answer):
    all_value_Rates = {}
    for i in ["EUR", "USD"]: 
        answer_currency_Rate, date = find_currency(i, answer)
        value_Rate = {
            answer_currency_Rate.get("currency"): {
                "sale": answer_currency_Rate.get("saleRate"), 
                "purchase": answer_currency_Rate.get("purchaseRate")
            }
        }
        all_value_Rates.update(value_Rate)

    output = {
        date: all_value_Rates
        }
    write_json_file(output) 
    print([output])
    return             

async def quantity_days(num):
    if 0 <= int(num) <= 10: 
        await date_param(num)
    else:    
        print("Quantity days must be between 1 and 10")
    return None


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f'{ws.remote_address} connects')

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f'{ws.remote_address} disconnects')

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def send_to_client(self, message: str, ws: WebSocketServerProtocol):
        await ws.send(message)

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            if message == 'exchange':
                r = await quantity_days()
                # await self.send_to_clients(r)
                await self.send_to_client(r, ws)
            else:
                await self.send_to_clients(f"{ws.name}: {message}")


async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, 'localhost', 8080):
        await asyncio.Future()  # run forever


if __name__ == '__main__':
    asyncio.run(main())