from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Registro(Base):
    """
    Modelo para a tabela 'registros'.
    """

    __tablename__ = "registros"

    id = Column(Integer, primary_key=True, index=True)
    colaborador = Column(String, nullable=False)
    orgao_publico = Column(String, nullable=False)
    figura_publica = Column(String, nullable=False)
    cargo = Column(String, nullable=True)  # Permitir nulos
    assunto = Column(String, nullable=False)
    municipio = Column(String, nullable=False)
    data = Column(DateTime, nullable=False)
    foto = Column(String, nullable=True)  # Permitir nulos
    criado_em = Column(DateTime, server_default=func.now())  # Adiciona a data de criação
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())  # Adiciona a data de atualização

    demandas = relationship("Demanda", back_populates="registro")


class Demanda(Base):
    """
    Modelo para a tabela 'demandas'.
    """

    __tablename__ = "demandas"

    id = Column(Integer, primary_key=True, index=True)
    registro_id = Column(Integer, ForeignKey("registros.id"), nullable=False)
    texto = Column(String, nullable=False)
    ov = Column(String, nullable=True)  # Permitir nulos
    pro = Column(String, nullable=True)  # Permitir nulos
    observacao = Column(String, nullable=True)  # Permitir nulos
    criado_em = Column(DateTime, server_default=func.now())  # Adiciona a data de criação
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())  # Adiciona a data de atualização

    registro = relationship("Registro", back_populates="demandas")