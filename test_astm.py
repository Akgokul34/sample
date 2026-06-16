import asyncio

def calculate_checksum(frame_data: bytes) -> bytes:
    chksum = sum(frame_data) % 256
    return f"{chksum:02X}".encode()

async def simulate_machine():
    print("Connecting to TCP Server...")
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', 5601)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print("Sending ENQ (0x05)...")
    writer.write(b'\x05')
    await writer.drain()

    ack = await reader.read(1)
    if ack == b'\x06':
        print("Received ACK (0x06)! Server is ready.")
        
        # Construct a real frame
        text_data = b"1H|\\^&|||Simulator|||||||P|1\r"
        frame_num = b"1"
        etx = b'\x03'
        
        # Calculate checksum on [FrameNum] + [Data] + [ETX]
        data_for_cs = frame_num + text_data + etx
        cs = calculate_checksum(data_for_cs)
        
        # Assemble full frame: STX + data_for_cs + CS + CR + LF
        full_frame = b'\x02' + data_for_cs + cs + b'\x0D\x0A'
        
        print(f"Sending Frame: {full_frame}")
        writer.write(full_frame)
        await writer.drain()
        
        ack2 = await reader.read(1)
        if ack2 == b'\x06':
            print("Received ACK for Frame! Checksum was validated correctly.")
        elif ack2 == b'\x15': # NAK
            print("Received NAK for Frame. Checksum failed!")
            
        print("Sending EOT (0x04)...")
        writer.write(b'\x04')
        await writer.drain()
    else:
        print(f"Received unexpected byte: {ack}")

    writer.close()
    await writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(simulate_machine())
