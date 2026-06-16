import asyncio
import logging

logger = logging.getLogger(__name__)

# ASTM E1381 Control Characters
ENQ = b'\x05'
ACK = b'\x06'
NAK = b'\x15'
EOT = b'\x04'
STX = b'\x02'
ETX = b'\x03'
ETB = b'\x17'
CR  = b'\x0D'
LF  = b'\x0A'

class ASTMStateMachine:
    def __init__(self):
        self.state = "IDLE"
        self.buffer = bytearray()
        self.intermediate_buffer = bytearray()
        self.expected_frame_number = 1

    def calculate_checksum(self, frame_data: bytes) -> bytes:
        """
        Calculates ASTM checksum: sum of bytes modulo 256, hex encoded.
        frame_data MUST include everything after STX up to and including ETX/ETB.
        """
        chksum = sum(frame_data) % 256
        return f"{chksum:02X}".encode()

    async def _transmit_astm_message(self, message: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Sends an ASTM message back to the machine as a host, with NAK retries."""
        logger.info("Transmitting Host Query Response")
        max_retries = 6
        
        # 1. Send ENQ
        for attempt in range(max_retries):
            writer.write(ENQ)
            await writer.drain()
            try:
                ack = await asyncio.wait_for(reader.read(1), timeout=15.0)
                if ack == ACK:
                    break
                elif ack == NAK:
                    logger.warning(f"Received NAK for ENQ (attempt {attempt+1}/{max_retries})")
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.error(f"Expected ACK, got {ack}")
                    return
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for ACK after ENQ")
                return
        else:
            logger.error("Max retries exceeded for ENQ")
            return
            
        # 2. Send Frame
        frame_num = b"1"
        data_for_cs = frame_num + message.encode() + ETX
        cs = self.calculate_checksum(data_for_cs)
        frame = STX + data_for_cs + cs + CR + LF
        
        for attempt in range(max_retries):
            writer.write(frame)
            await writer.drain()
            try:
                ack = await asyncio.wait_for(reader.read(1), timeout=15.0)
                if ack == ACK:
                    break
                elif ack == NAK:
                    logger.warning(f"Received NAK for Frame (attempt {attempt+1}/{max_retries})")
                    continue
            except asyncio.TimeoutError:
                logger.error("Timeout waiting for ACK after Frame")
                return
        else:
            logger.error("Max retries exceeded for Frame")
            return
            
        # 3. Send EOT
        writer.write(EOT)
        await writer.drain()
        logger.info("Host Query Response transmission complete")

    async def handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Implements the strict E1381 low-level transport.
        """
        addr = writer.get_extra_info('peername')
        ip_address = addr[0]
        logger.info(f"ASTM Session started for {addr}")
        
        from backend.app.core.database import AsyncSessionLocal
        from backend.app.models.machine import Machine, ConnectionLog, RawMessage
        from sqlalchemy.future import select
        
        # 1. Machine Identity Lookup
        machine_id = None
        async with AsyncSessionLocal() as session:
            stmt = select(Machine).where(Machine.ip_address == ip_address)
            result = await session.execute(stmt)
            machine = result.scalars().first()
            
            if not machine or not machine.is_active or machine.protocol.upper() != "ASTM":
                logger.error(f"Rejecting unauthorized ASTM connection from {ip_address}")
                writer.close()
                await writer.wait_closed()
                return
            else:
                machine_id = str(machine.id)
                logger.info(f"Machine {machine.name} ({machine_id}) connected.")
                
                # Log connection
                conn_log = ConnectionLog(machine_id=machine_id, ip_address=ip_address, port=addr[1], status="connected")
                session.add(conn_log)
                await session.commit()
                
        try:
            while True:
                # 2. Add Timeout to prevent dead sockets hanging forever
                try:
                    char = await asyncio.wait_for(reader.read(1), timeout=30.0)
                except asyncio.TimeoutError:
                    logger.error("Session timed out waiting for data. Closing connection.")
                    break
                    
                if not char:
                    break

                if char == ENQ:
                    logger.info("Received ENQ, sending ACK")
                    writer.write(ACK)
                    await writer.drain()
                    self.state = "RECEIVING"
                    self.expected_frame_number = 1
                    self.buffer.clear()
                
                elif char == STX and self.state == "RECEIVING":
                    # Read until CR LF with timeout
                    try:
                        rest_of_frame = await asyncio.wait_for(reader.readuntil(CR + LF), timeout=15.0)
                    except asyncio.TimeoutError:
                        logger.error("Timeout reading frame. Sending NAK.")
                        writer.write(NAK)
                        await writer.drain()
                        continue
                    
                    if len(rest_of_frame) < 5:
                        logger.warning("Frame too short, sending NAK")
                        writer.write(NAK)
                        await writer.drain()
                        continue
                        
                    # Extract parts
                    frame_num = rest_of_frame[0:1]
                    received_checksum = rest_of_frame[-4:-2]
                    
                    # Data used for checksum calculation (FrameNum + Data + ETX/ETB)
                    data_for_checksum = rest_of_frame[:-4]
                    calculated_checksum = self.calculate_checksum(data_for_checksum)
                    terminator = data_for_checksum[-1:]
                    
                    # 3. Frame Validation
                    try:
                        incoming_frame_num = int(frame_num.decode())
                        if incoming_frame_num != self.expected_frame_number:
                            logger.error(f"Frame number mismatch! Expected {self.expected_frame_number}, got {incoming_frame_num}. Sending NAK.")
                            writer.write(NAK)
                            await writer.drain()
                            continue
                    except ValueError:
                        pass # Non-integer frame number, handle gracefully via checksum failure
                    
                    if received_checksum != calculated_checksum:
                        logger.error(f"Checksum mismatch! Expected {calculated_checksum.decode()}, got {received_checksum.decode()}. Sending NAK.")
                        writer.write(NAK)
                        await writer.drain()
                        continue

                    logger.info(f"Frame {frame_num.decode()} received and validated. Sending ACK.")
                    
                    # Extract the actual text payload (remove FrameNum and ETX/ETB)
                    text_payload = rest_of_frame[1:-5]
                    self.intermediate_buffer.extend(text_payload)
                    
                    writer.write(ACK)
                    await writer.drain()
                    
                    # Increment expected frame number (1-7, then 0)
                    self.expected_frame_number = (self.expected_frame_number % 8) + 1
                    
                    if terminator == ETX:
                        self.buffer.extend(self.intermediate_buffer)
                        self.intermediate_buffer.clear()
                    elif terminator == ETB:
                        logger.info("Received ETB. Waiting for more frames.")
                    
                elif char == EOT and self.state == "RECEIVING":
                    logger.info("Received EOT, transmission complete.")
                    self.state = "IDLE"
                    
                    raw_msg = self.buffer.decode(errors='ignore')
                    logger.info(f"Complete message received: {raw_msg}")
                    
                    # Store Raw Message
                    async with AsyncSessionLocal() as session:
                        raw_log = RawMessage(machine_id=machine_id, direction="inbound", payload=raw_msg)
                        session.add(raw_log)
                        await session.commit()
                    
                    try:
                        from drivers.impl.generic_astm import GenericASTMDriver
                        driver = GenericASTMDriver({})
                        response_order = await driver.process_message(raw_msg, machine_id)
                        
                        if response_order:
                            await self._transmit_astm_message(response_order, reader, writer)
                    except Exception as e:
                        logger.error(f"Failed to process ASTM message via Driver: {e}")
                        
                    self.buffer.clear()
                    
                else:
                    # Ignore other characters like keepalives or junk outside transmission
                    pass
                    
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logger.error(f"Error in ASTM session: {e}")
        finally:
            # Log disconnection
            if machine_id:
                async with AsyncSessionLocal() as session:
                    conn_log = ConnectionLog(machine_id=machine_id, ip_address=ip_address, port=addr[1], status="disconnected")
                    session.add(conn_log)
                    await session.commit()
