from fastapi import FastAPI
import os

app = FastAPI()

@app.get("/export")
def exportar():
    os.system("python export_to_excel.py")
    return {"status": "Exportação iniciada"}
