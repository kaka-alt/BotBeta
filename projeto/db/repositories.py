from sqlalchemy.orm import Session
from typing import List, Optional
from db import models


class RegistroRepository:
    """
    Repositório para a entidade Registro.
    Abstrai o acesso aos dados da tabela 'registros'.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_registro_por_id(self, registro_id: int) -> Optional[models.Registro]:
        return self.db.query(models.Registro).filter(models.Registro.id == registro_id).first()

    def listar_registros(self, skip: int = 0, limit: int = 100) -> List[models.Registro]:
        return self.db.query(models.Registro).offset(skip).limit(limit).all()

    def criar_registro(self, registro: dict) -> models.Registro:
        db_registro = models.Registro(**registro)  # Desempacota o dicionário para criar o objeto Registro
        self.db.add(db_registro)
        self.db.commit()
        self.db.refresh(db_registro)  # Atualiza o objeto com os valores do banco (como o ID gerado)
        return db_registro

    def atualizar_registro(self, registro_id: int, registro_atualizacao: dict) -> Optional[models.Registro]:
        db_registro = self.get_registro_por_id(registro_id)
        if db_registro:
            for key, value in registro_atualizacao.items():
                setattr(db_registro, key, value)  # Atualiza os atributos do objeto
            self.db.commit()
            self.db.refresh(db_registro)
        return db_registro

    def deletar_registro(self, registro_id: int) -> bool:
        db_registro = self.get_registro_por_id(registro_id)
        if db_registro:
            self.db.delete(db_registro)
            self.db.commit()
            return True
        return False


class DemandaRepository:
    """
    Repositório para a entidade Demanda.
    Abstrai o acesso aos dados da tabela 'demandas'.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_demanda_por_id(self, demanda_id: int) -> Optional[models.Demanda]:
        return self.db.query(models.Demanda).filter(models.Demanda.id == demanda_id).first()

    def listar_demandas(self, skip: int = 0, limit: int = 100) -> List[models.Demanda]:
        return self.db.query(models.Demanda).offset(skip).limit(limit).all()

    def criar_demanda(self, demanda: dict) -> models.Demanda:
        db_demanda = models.Demanda(**demanda)
        self.db.add(db_demanda)
        self.db.commit()
        self.db.refresh(db_demanda)
        return db_demanda

    def atualizar_demanda(self, demanda_id: int, demanda_atualizacao: dict) -> Optional[models.Demanda]:
        db_demanda = self.get_demanda_por_id(demanda_id)
        if db_demanda:
            for key, value in demanda_atualizacao.items():
                setattr(db_demanda, key, value)
            self.db.commit()
            self.db.refresh(db_demanda)
        return db_demanda

    def deletar_demanda(self, demanda_id: int) -> bool:
        db_demanda = self.get_demanda_por_id(demanda_id)
        if db_demanda:
            self.db.delete(db_demanda)
            self.db.commit()
            return True
        return False