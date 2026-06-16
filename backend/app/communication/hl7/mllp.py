import asyncio
import logging
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.machine import Machine, ConnectionLog, RawMessage
from sqlalchemy.future import select

logger = logging.getLogger(__name__)

VT = b'\x0B'
FS = b'\x1C'
CR = b'\x0D'

async def mllp_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    Handles unwrapping MLLP (Minimal Lower Layer Protocol) for HL7.
    Format: <VT> [HL7 Message] <FS> <CR>
    """
    addr = writer.get_extra_info('peername')
    ip_address = addr[0]
    logger.info(f"HL7 Session started for {addr}")
    
    # 1. Machine Identity Lookup
    machine_id = None
    async with AsyncSessionLocal() as session:
        stmt = select(Machine).where(Machine.ip_address == ip_address)
        result = await session.execute(stmt)
        machine = result.scalars().first()
        
        if not machine or not machine.is_active or machine.protocol.upper() != "HL7":
            logger.error(f"Rejecting unauthorized HL7 connection from {ip_address}")
            writer.close()
            await writer.wait_closed()
            return
        else:
            machine_id = str(machine.id)
            logger.info(f"Machine {machine.name} ({machine_id}) connected via MLLP.")
            
            # Log connection
            conn_log = ConnectionLog(machine_id=machine_id, ip_address=ip_address, port=addr[1], status="connected")
            session.add(conn_log)
            await session.commit()

    try:
        while True:
            # Enforce strict <VT> parsing and timeouts
            try:
                char = await asyncio.wait_for(reader.read(1), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error("Session timed out waiting for data. Closing connection.")
                break
                
            if not char:
                break
                
            if char != VT:
                logger.error(f"Invalid MLLP start byte received: {char}. Dropping connection to prevent stream corruption.")
                break
            
            # Read until the FS + CR block
            try:
                message = await asyncio.wait_for(reader.readuntil(FS + CR), timeout=15.0)
            except asyncio.TimeoutError:
                logger.error("Timeout reading HL7 frame. Closing connection.")
                break
                
            # Strip the envelope
            hl7_data_bytes = message[:-2]
            hl7_data = hl7_data_bytes.decode(errors='ignore')
            logger.info(f"Received HL7 Message:\n{hl7_data}")
            
            # Save Raw Message
            async with AsyncSessionLocal() as session:
                raw_log = RawMessage(machine_id=machine_id, direction="inbound", payload=hl7_data)
                session.add(raw_log)
                await session.commit()
            
            try:
                from drivers.impl.generic_hl7 import GenericHL7Driver
                driver = GenericHL7Driver({})
                ack_message = await driver.process_message(hl7_data, machine_id)
                
                if ack_message:
                    logger.info(f"Sending ACK:\n{ack_message}")
                    writer.write(VT + ack_message.encode() + FS + CR)
                    await writer.drain()
                    
                    # Log outbound ACK
                    async with AsyncSessionLocal() as session:
                        raw_log = RawMessage(machine_id=machine_id, direction="outbound", payload=ack_message)
                        session.add(raw_log)
                        await session.commit()
                        
            except Exception as e:
                logger.error(f"Error processing HL7 message via Driver: {e}")
                
    except asyncio.IncompleteReadError:
        pass
    except Exception as e:
        logger.error(f"Error in HL7 session: {e}")
    finally:
        # Log disconnection
        if machine_id:
            async with AsyncSessionLocal() as session:
                conn_log = ConnectionLog(machine_id=machine_id, ip_address=ip_address, port=addr[1], status="disconnected")
                session.add(conn_log)
                await session.commit()
        writer.close()
        await writer.wait_closed()
