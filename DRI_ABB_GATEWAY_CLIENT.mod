MODULE DRI_ABB_GATEWAY_CLIENT

    PERS string dri_gateway_ip := "192.168.0.10";
    PERS num dri_gateway_port := 6101;

    VAR socketdev dri_socket;
    VAR bool dri_connected := FALSE;

    VAR string dri_rx := "";
    VAR num dri_status := 9;
    VAR num dri_cell := 0;
    VAR num dri_part := 0;
    VAR num dri_confidence := 0;

    PROC DRI_Connect()
        IF dri_connected THEN
            RETURN;
        ENDIF

        SocketCreate dri_socket;
        SocketConnect dri_socket, dri_gateway_ip, dri_gateway_port \Time:=5;
        dri_connected := TRUE;
    ERROR
        dri_connected := FALSE;
        SocketClose dri_socket;
        dri_status := 9;
        RETURN;
    ENDPROC

    PROC DRI_Disconnect()
        IF dri_connected THEN
            SocketClose dri_socket;
        ENDIF
        dri_connected := FALSE;
    ENDPROC

    PROC DRI_GetNext()
        DRI_Connect;

        IF NOT dri_connected THEN
            dri_status := 9;
            dri_cell := 0;
            dri_part := 0;
            dri_confidence := 0;
            RETURN;
        ENDIF

        SocketSend dri_socket \Str:="GET_NEXT";
        SocketReceive dri_socket \Str:=dri_rx \ReadNoOfBytes:=11 \Time:=2;
        DRI_ParseCompact;
    ERROR
        DRI_Disconnect;
        dri_status := 9;
        dri_cell := 0;
        dri_part := 0;
        dri_confidence := 0;
        RETURN;
    ENDPROC

    PROC DRI_ParseCompact()
        VAR bool ok_status;
        VAR bool ok_cell;
        VAR bool ok_part;
        VAR bool ok_conf;

        ok_status := StrToVal(StrPart(dri_rx, 1, 1), dri_status);
        ok_cell := StrToVal(StrPart(dri_rx, 3, 2), dri_cell);
        ok_part := StrToVal(StrPart(dri_rx, 6, 2), dri_part);
        ok_conf := StrToVal(StrPart(dri_rx, 9, 3), dri_confidence);

        IF NOT ok_status OR NOT ok_cell OR NOT ok_part OR NOT ok_conf THEN
            dri_status := 9;
            dri_cell := 0;
            dri_part := 0;
            dri_confidence := 0;
        ENDIF
    ENDPROC

    FUNC bool DRI_TargetValid()
        RETURN dri_status = 1;
    ENDFUNC

    FUNC bool DRI_BoardEmpty()
        RETURN dri_status = 0;
    ENDFUNC

    FUNC bool DRI_TargetUncertain()
        RETURN dri_status = 2;
    ENDFUNC

    FUNC bool DRI_Error()
        RETURN dri_status = 9;
    ENDFUNC

ENDMODULE
