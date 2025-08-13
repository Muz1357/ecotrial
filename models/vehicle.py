# models/vehicle.py
from datetime import datetime
from models.db import get_connection

class Vehicle:
    def __init__(self, id=None, owner_id=None, model_name=None, plate_number=None, 
                 rate_per_km=0, points_per_km=0, proof_path=None, vehicle_type=None,
                 approval_status='pending', created_at=None, updated_at=None):
        self.id = id
        self.owner_id = owner_id
        self.model_name = model_name
        self.plate_number = plate_number
        self.rate_per_km = rate_per_km
        self.points_per_km = points_per_km
        self.proof_path = proof_path
        self.vehicle_type = vehicle_type
        self.approval_status = approval_status
        self.created_at = created_at if created_at else datetime.utcnow()
        self.updated_at = updated_at if updated_at else datetime.utcnow()

    @staticmethod
    def from_dict(data):
        return Vehicle(
            id=data.get('id'),
            owner_id=data.get('owner_id'),
            model_name=data.get('model_name'),
            plate_number=data.get('plate_number'),
            rate_per_km=data.get('rate_per_km', 0),
            points_per_km=data.get('points_per_km', 0),
            proof_path=data.get('proof_path'),
            vehicle_type=data.get('vehicle_type'),
            approval_status=data.get('approval_status', 'pending'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

    def to_dict(self):
        return {
            'id': self.id,
            'owner_id': self.owner_id,
            'model_name': self.model_name,
            'plate_number': self.plate_number,
            'rate_per_km': float(self.rate_per_km) if self.rate_per_km else 0.0,
            'points_per_km': self.points_per_km,
            'proof_path': self.proof_path,
            'vehicle_type': self.vehicle_type,
            'approval_status': self.approval_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }