# DRI Robot Adapter Gateway for ABB and KUKA

This package separates the DRI camera algorithm from robot-specific communication.

## Architecture

DRI camera server
→ `dri_robot_gateway.py`
→ ABB or KUKA robot over TCP

The DRI server stays robot-independent and returns the generic compact target:

`S;CC;PP;QQQ`

Example:

`1;07;03;094`

Meaning:
- `S` = status
- `CC` = board cell
- `PP` = part ID
- `QQQ` = confidence

## ABB output

ABB receives the same compact format:

`1;07;03;094`

Run gateway for ABB:

```bash
python dri_robot_gateway.py serve \
  --dri-host 127.0.0.1 \
  --dri-port 5005 \
  --listen-host 0.0.0.0 \
  --listen-port 6101 \
  --format abb
```

Load `DRI_ABB_GATEWAY_CLIENT.mod` into the ABB controller and set:

```rapid
PERS string dri_gateway_ip := "192.168.0.10";
PERS num dri_gateway_port := 6101;
```

## KUKA output

KUKA receives XML:

```xml
<DRI>
  <Status>1</Status>
  <Cell>7</Cell>
  <Part>3</Part>
  <Confidence>94</Confidence>
</DRI>
```

Run gateway for KUKA:

```bash
python dri_robot_gateway.py serve \
  --dri-host 127.0.0.1 \
  --dri-port 5005 \
  --listen-host 0.0.0.0 \
  --listen-port 6102 \
  --format kuka_xml
```

Copy `DRI_GATEWAY.xml` to the KUKA EthernetKRL configuration folder and adapt the PC IP and port.

Use `DRI_KUKA_GATEWAY_CLIENT.src` as a starter KRL program.

## Running ABB and KUKA in parallel

```bash
python dri_robot_gateway.py serve --dri-host 127.0.0.1 --dri-port 5005 --listen-port 6101 --format abb
python dri_robot_gateway.py serve --dri-host 127.0.0.1 --dri-port 5005 --listen-port 6102 --format kuka_xml
```

Both robots can use the same DRI algorithm, but each receives the data in its preferred format.

## Test without robots

Assuming the DRI server is running on port 5005:

```bash
python dri_robot_gateway.py once --dri-host 127.0.0.1 --dri-port 5005 --format abb
python dri_robot_gateway.py once --dri-host 127.0.0.1 --dri-port 5005 --format kuka_xml
```
