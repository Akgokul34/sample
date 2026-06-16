import asyncio
import logging
from typing import AsyncGenerator, Tuple, Optional

logger = logging.getLogger(__name__)

# Control Characters
ENQ = b'\x05'
ACK = b'\x06'
NAK = b'\x15'
EOT = b'\x04'
STX = b'\x02'
ETX = b'\x03'
ETB = b'\x17'
CR  = b'\x0D'
LF  = b'\x0A'
VT  = b'\x0B'
FS  = b'\x1C'

def calculate_checksum(frame_data: bytes) -> bytes:
    chksum = sum(frame_data) % 256
    return f"{chksum:02X}".encode()

class VirtualMachine:
    def __init__(self, host: str = "127.0.0.1", port: int = 5601):
        self.host = host
        self.port = port

    def _assemble_frame(self, text_payload: bytes, frame_num: int, use_etb: bool = False, force_bad_checksum: bool = False) -> bytes:
        terminator = ETB if use_etb else ETX
        frame_num_byte = str(frame_num).encode()
        data_for_cs = frame_num_byte + text_payload + terminator
        
        if force_bad_checksum:
            cs = b"00"
        else:
            cs = calculate_checksum(data_for_cs)
            
        return STX + data_for_cs + cs + CR + LF

    async def run_simulation(
        self, 
        protocol: str, 
        scenario: str, 
        barcode: str,
        custom_results: Optional[dict] = None
    ) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Executes a real protocol simulation against the server.
        Yields (event_type, message) tuples to stream to the client.
        """
        target_port = self.port if protocol == "ASTM" else 5602
        
        yield "info", f"Initiating TCP connection to {self.host}:{target_port}"
        try:
            reader, writer = await asyncio.open_connection(self.host, target_port)
            yield "info", f"Successfully connected to LIS Server ({self.host}:{target_port})"
        except Exception as e:
            yield "error", f"Connection failed: {str(e)}"
            return

        try:
            if protocol == "ASTM":
                async for event in self._run_astm_simulation(reader, writer, scenario, barcode, custom_results):
                    yield event
            elif protocol == "HL7":
                async for event in self._run_hl7_simulation(reader, writer, scenario, barcode, custom_results):
                    yield event
        except Exception as e:
            yield "error", f"Simulation error: {str(e)}"
        finally:
            writer.close()
            try:
                await writer.wait_closed()
                yield "info", "Connection closed."
            except Exception:
                pass

    async def _run_astm_simulation(
        self, 
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter, 
        scenario: str, 
        barcode: str,
        custom_results: Optional[dict] = None
    ) -> AsyncGenerator[Tuple[str, str], None]:
        
        if scenario == "DISCONNECT":
            yield "info", "Scenario DISCONNECT: Dropping connection immediately."
            return

        # 1. Send ENQ
        yield "tx", "<ENQ> (0x05)"
        writer.write(ENQ)
        await writer.drain()

        if scenario == "TIMEOUT":
            yield "info", "Scenario TIMEOUT: Idling for 32 seconds to trigger server session timeout..."
            await asyncio.sleep(32)
            try:
                # Try reading to see if server disconnected us
                data = await asyncio.wait_for(reader.read(1), timeout=1.0)
                if not data:
                    yield "success", "Server successfully disconnected idle socket (correct behavior)."
                else:
                    yield "error", f"Server did not timeout! Received: {data}"
            except asyncio.TimeoutError:
                yield "error", "Server did not disconnect idle socket within 32 seconds."
            return

        # Read ACK
        try:
            ack = await asyncio.wait_for(reader.read(1), timeout=5.0)
        except asyncio.TimeoutError:
            yield "error", "Timeout waiting for ACK after ENQ"
            return

        if ack == ACK:
            yield "rx", "<ACK> (0x06)"
        else:
            yield "error", f"Expected <ACK>, got {ack!r}"
            return

        # Determine if we are doing Host Query or Result Upload
        is_result_upload = (scenario == "RESULT_UPLOAD" or custom_results is not None)

        if not is_result_upload:
            # --- ASTM HOST QUERY ---
            # 2. Send Header
            header = b"H|\\^&|||Simulator|||||||P|1\r"
            frame1 = self._assemble_frame(header, 1, force_bad_checksum=(scenario == "BAD_CHECKSUM"))
            
            yield "tx", f"Header Frame (Frame 1): {header.decode().strip()}"
            writer.write(frame1)
            await writer.drain()

            try:
                resp = await asyncio.wait_for(reader.read(1), timeout=5.0)
            except asyncio.TimeoutError:
                yield "error", "Timeout waiting for ACK/NAK after Header"
                return

            if resp == ACK:
                yield "rx", "<ACK> (0x06)"
                if scenario == "BAD_CHECKSUM":
                    yield "error", "Server accepted corrupt checksum! (Expected NAK)"
                    return
            elif resp == NAK:
                yield "rx", "<NAK> (0x15)"
                if scenario == "BAD_CHECKSUM":
                    yield "success", "Server successfully rejected corrupt checksum with <NAK> (correct behavior)."
                    # Re-send correct frame to heal and continue
                    yield "info", "Retrying with corrected checksum..."
                    frame1_correct = self._assemble_frame(header, 1)
                    yield "tx", f"Corrected Header Frame (Frame 1): {header.decode().strip()}"
                    writer.write(frame1_correct)
                    await writer.drain()
                    resp_retry = await reader.read(1)
                    if resp_retry == ACK:
                        yield "rx", "<ACK> (0x06) [Accepted]"
                    else:
                        yield "error", "Retried frame also rejected."
                        return
                else:
                    yield "error", "Server rejected Header frame with <NAK>"
                    return

            # 3. Send Query
            query = f"Q|1|^{barcode}||ALL||||||||O\r".encode()
            frame2 = self._assemble_frame(query, 2)
            yield "tx", f"Query Frame (Frame 2): {query.decode().strip()}"
            writer.write(frame2)
            await writer.drain()

            resp = await reader.read(1)
            if resp == ACK:
                yield "rx", "<ACK> (0x06)"
            else:
                yield "error", f"Server rejected Query frame: {resp!r}"
                return

            # 4. Send EOT
            yield "tx", "<EOT> (0x04)"
            writer.write(EOT)
            await writer.drain()

            # 5. Wait for Host Query Response on same connection
            yield "info", "Awaiting Host Query Response from LIS Server..."
            try:
                server_enq = await asyncio.wait_for(reader.read(1), timeout=5.0)
                if server_enq == ENQ:
                    yield "rx", "<ENQ> (0x05) [Server initiating transmission]"
                    yield "tx", "<ACK> (0x06)"
                    writer.write(ACK)
                    await writer.drain()

                    # Read server response frames
                    while True:
                        char = await asyncio.wait_for(reader.read(1), timeout=5.0)
                        if not char:
                            break
                        if char == EOT:
                            yield "rx", "<EOT> (0x04) [Server finished transmission]"
                            yield "success", "Bidirectional Host Query transaction completed successfully."
                            break
                        elif char == STX:
                            # Read rest of frame
                            rest = await asyncio.wait_for(reader.readuntil(CR + LF), timeout=5.0)
                            yield "rx", f"<STX>{rest.decode(errors='ignore').strip()}"
                            yield "tx", "<ACK> (0x06)"
                            writer.write(ACK)
                            await writer.drain()
                else:
                    yield "error", f"Server did not initiate Host Query Response; received: {server_enq!r}"
            except asyncio.TimeoutError:
                yield "error", "Timeout waiting for Server Host Query Response."

        else:
            # --- ASTM RESULT UPLOAD ---
            res_data = custom_results or {"code": "WBC", "val": "7.5", "unit": "10^3/uL"}
            test_code = res_data.get("code", "WBC")
            value = res_data.get("val", "7.5")
            unit = res_data.get("unit", "10^3/uL")

            # Records
            header = b"H|\\^&|||Simulator|||||||P|1\r"
            patient = f"P|1||PT-999||Smith^John|||M\r".encode()
            order = f"O|1|{barcode}||{test_code}\r".encode()
            result = f"R|1|{test_code}|{value}|{unit}|||N\r".encode()

            frames = [
                (header, 1),
                (patient, 2),
                (order, 3),
                (result, 4)
            ]

            for payload, num in frames:
                frame = self._assemble_frame(payload, num)
                yield "tx", f"Sending Frame {num}: {payload.decode().strip()}"
                writer.write(frame)
                await writer.drain()

                resp = await asyncio.wait_for(reader.read(1), timeout=5.0)
                if resp == ACK:
                    yield "rx", "<ACK> (0x06)"
                else:
                    yield "error", f"Frame {num} rejected with: {resp!r}"
                    return

            # EOT
            yield "tx", "<EOT> (0x04)"
            writer.write(EOT)
            await writer.drain()
            yield "success", f"Successfully uploaded test results ({test_code}={value} {unit}) for barcode {barcode}."


    async def _run_hl7_simulation(
        self, 
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter, 
        scenario: str, 
        barcode: str,
        custom_results: Optional[dict] = None
    ) -> AsyncGenerator[Tuple[str, str], None]:
        
        if scenario == "DISCONNECT":
            yield "info", "Scenario DISCONNECT: Dropping connection immediately."
            return

        res_data = custom_results or {"code": "WBC", "val": "7.5", "unit": "10^3/uL"}
        test_code = res_data.get("code", "WBC")
        value = res_data.get("val", "7.5")
        unit = res_data.get("unit", "10^3/uL")

        # Delimiters
        fs = "|"
        comp = "^~\\&"
        if scenario == "HL7_ALT_SEP":
            fs = "/"
            comp = "*~\\&"
            yield "info", "Scenario HL7_ALT_SEP: Using custom delimiters ('/' field separator, '*' component separator)"

        msh = f"MSH{fs}{comp}{fs}Simulator{fs}LIS{fs}LIC{fs}LIS{fs}20240616120000{fs}{fs}ORU^R01{fs}MSG-{barcode}{fs}P{fs}2.3"
        pid = f"PID{fs}1{fs}{fs}PT-888{fs}{fs}Doe^Jane{fs}{fs}19850505"
        obr = f"OBR{fs}1{fs}{fs}{barcode}"
        obx = f"OBX{fs}1{fs}ST{fs}{test_code}{fs}{fs}{value}{fs}{unit}{fs}{fs}{fs}{fs}{fs}F"

        hl7_msg = f"{msh}\r{pid}\r{obr}\r{obx}\r"

        if scenario == "HL7_BAD_FRAME":
            yield "info", "Scenario HL7_BAD_FRAME: Sending HL7 payload WITHOUT start byte <VT>..."
            writer.write(hl7_msg.encode() + FS + CR)
        else:
            yield "tx", f"Sending HL7 Message:\n{hl7_msg.replace(chr(13), chr(10))}"
            writer.write(VT + hl7_msg.encode() + FS + CR)
            
        await writer.drain()

        yield "info", "Awaiting HL7 ACK Response..."
        try:
            # Read response
            char = await asyncio.wait_for(reader.read(1), timeout=5.0)
            if not char:
                yield "info", "Server disconnected."
                if scenario == "HL7_BAD_FRAME":
                    yield "success", "Server successfully rejected bad envelope by closing connection (correct behavior)."
                else:
                    yield "error", "Server disconnected before sending ACK."
                return
                
            if char != VT:
                yield "error", f"Invalid MLLP start byte from server: {char!r}"
                return
                
            ack_data_bytes = await asyncio.wait_for(reader.readuntil(FS + CR), timeout=5.0)
            ack_msg = ack_data_bytes[:-2].decode(errors='ignore')
            yield "rx", f"Received HL7 ACK:\n{ack_msg.replace(chr(13), chr(10))}"
            
            # Check MSA code
            if "MSA|AA" in ack_msg or "MSA/AA" in ack_msg:
                yield "success", "HL7 Message accepted by server (MSA Code: AA)."
            else:
                yield "error", "HL7 Message rejected or returned error."
                
        except asyncio.TimeoutError:
            yield "error", "Timeout waiting for HL7 ACK."
        except asyncio.IncompleteReadError:
            yield "info", "Connection closed by LIS server."
