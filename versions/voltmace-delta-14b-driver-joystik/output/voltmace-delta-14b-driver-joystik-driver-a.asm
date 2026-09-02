; Memory locations
bytev    = &020a
; &020a referenced 1 time by &0a03
bytev_hi = &020b
; &020b referenced 1 time by &0a08
osbyte   = &fff4
; &fff4 referenced 3 times by &0a66, &0a72, &0a83


    org &0a00

.dasmos_start
; ***************************************************************************************
; Install the resident joystick driver
;
; Point BYTEV at the OSBYTE intercept at &0A0D. Called from the BASIC via CALL &A00,
; after it has saved the previous BYTEV (line 50) and patched the chain slot (line 1840)
; and sensitivity thresholds (line 1850).
.install
    pha                                                               ; 0a00: 48          H        ; Preserve A
    lda #&0d                                                          ; 0a01: a9 0d       ..       ; BYTEV low byte -> &0D...
    sta bytev                                                         ; 0a03: 8d 0a 02    ...      ; store it
    lda #&0a                                                          ; 0a06: a9 0a       ..       ; ...high byte -> &0A...
    sta bytev_hi                                                      ; 0a08: 8d 0b 02    ...      ; ...so every OSBYTE now enters the handler at &0A0D
    pla                                                               ; 0a0b: 68          h        ; Restore A
    rts                                                               ; 0a0c: 60          `        ; Return to the BASIC caller
; ***************************************************************************************
; BYTEV handler: map the joystick to INKEY
;
; Runs on every OSBYTE; only OSBYTE &81 (INKEY / read key) is intercepted. If the key
; being tested matches an entry in joystick_map, the matching analogue input is read and,
; when active, a "key pressed" result is returned; every other call chains to the
; previous BYTEV.
.osbyte_intercept
    cmp #&81                                                          ; 0a0d: c9 81       ..       ; Only intercept OSBYTE &81 (INKEY / read key)
    bne chain                                                         ; 0a0f: d0 2c       .,       ; other reason codes -> chain to the previous handler
    pha                                                               ; 0a11: 48          H        ; Preserve A (reason code)...
    tya                                                               ; 0a12: 98          .        ; Preserve Y (INKEY high byte)...
    pha                                                               ; 0a13: 48          H        ; on the stack
    txa                                                               ; 0a14: 8a          .        ; A := X = the INKEY key number being tested
    pha                                                               ; 0a15: 48          H        ; ...(X also preserved)
    ldy #0                                                            ; 0a16: a0 00       ..       ; No match yet...
    sty result_flag                                                   ; 0a18: 8c 98 0a    ...      ; ...clear the result flag
; &0a1b referenced 1 time by &0a2b
.scan_map
    cmp joystick_map,y                                                ; 0a1b: d9 b0 0a    ...      ; Does the tested key match this map entry?
    bne scan_next                                                     ; 0a1e: d0 03       ..       ; no -> skip it
    jsr read_joystick                                                 ; 0a20: 20 4b 0a     K.      ; yes -> read the joystick input for it
; &0a23 referenced 1 time by &0a1e
.scan_next
    iny                                                               ; 0a23: c8          .        ; Step over the 2-byte entry...
    iny                                                               ; 0a24: c8          .        ; twice
    cpy #8                                                            ; 0a25: c0 08       ..       ; first (button) block done?
    beq skip_to_directions                                            ; 0a27: f0 17       ..       ; yes -> jump to the direction block
; &0a29 referenced 1 time by &0a49
.scan_more
    cpy #&18                                                          ; 0a29: c0 18       ..       ; End of the map?
    bne scan_map                                                      ; 0a2b: d0 ee       ..       ; no -> keep scanning
    lda result_flag                                                   ; 0a2d: ad 98 0a    ...      ; Did any mapped input read as active?
    beq not_pressed                                                   ; 0a30: f0 06       ..       ; no -> return the normal INKEY result
    tax                                                               ; 0a32: aa          .        ; yes: return "key pressed" (X=Y=&FF)...
    tay                                                               ; 0a33: a8          .        ; X and Y
    pla                                                               ; 0a34: 68          h        ; drop the saved X...
    pla                                                               ; 0a35: 68          h        ; ...Y...
    pla                                                               ; 0a36: 68          h        ; ...A
    rts                                                               ; 0a37: 60          `        ; and return, claiming the OSBYTE
; &0a38 referenced 1 time by &0a30
.not_pressed
    pla                                                               ; 0a38: 68          h        ; Restore X...
    tax                                                               ; 0a39: aa          .        ; into X
    pla                                                               ; 0a3a: 68          h        ; Restore Y...
    tay                                                               ; 0a3b: a8          .        ; into Y
    pla                                                               ; 0a3c: 68          h        ; Restore A
; &0a3d referenced 1 time by &0a0f
.chain
    jmp chain_to_old_bytev                                            ; 0a3d: 4c fa 0a    L..      ; Pass the call to the previous BYTEV (chain slot below)
; &0a40 referenced 1 time by &0a27
.skip_to_directions
    iny                                                               ; 0a40: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a41: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a42: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a43: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a44: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a45: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a46: c8          .        ; skip the 8-byte button block
    iny                                                               ; 0a47: c8          .        ; skip the 8-byte button block
    clc                                                               ; 0a48: 18          .        ; clear carry for the branch
    bcc scan_more                                                     ; 0a49: 90 de       ..       ; resume scanning the direction entries
; ***************************************************************************************
; Test one analogue input
;
; For the matched entry, read its analogue channel with OSBYTE &80 (ADVAL) and compare
; the value against the sensitivity thresholds (a direction) or AND the fire-button bits
; (a button); flag a hit in result_flag.
; &0a4b referenced 1 time by &0a20
.read_joystick
    pha                                                               ; 0a4b: 48          H        ; Preserve A...
    tya                                                               ; 0a4c: 98          .        ; Preserve Y...
    pha                                                               ; 0a4d: 48          H        ; on the stack
    iny                                                               ; 0a4e: c8          .        ; Point at the entry parameter
    lda joystick_map,y                                                ; 0a4f: b9 b0 0a    ...      ; top nibble = ADC channel...
    and #&f0                                                          ; 0a52: 29 f0       ).       ; mask the top nibble
    lsr a                                                             ; 0a54: 4a          J        ; ...shift it down
    lsr a                                                             ; 0a55: 4a          J        ; ...shift it down
    lsr a                                                             ; 0a56: 4a          J        ; ...shift it down
    lsr a                                                             ; 0a57: 4a          J        ; ...shift it down
    tax                                                               ; 0a58: aa          .        ; ...into X for OSBYTE &80
    lda joystick_map,y                                                ; 0a59: b9 b0 0a    ...      ; reload the parameter
    cpy #&10                                                          ; 0a5c: c0 10       ..       ; direction entry (>= &10) or a fire button?
    bcs test_button                                                   ; 0a5e: b0 1c       ..       ; > = &10 -> the fire-button path
    and #1                                                            ; 0a60: 29 01       ).       ; low bit picks which threshold (push vs pull)
    beq test_high_threshold                                           ; 0a62: f0 0c       ..       ; else test the high threshold
    lda #&80                                                          ; 0a64: a9 80       ..       ; OSBYTE &80: read ADC channel X (ADVAL, Y=high byte)...
    jsr osbyte                                                        ; 0a66: 20 f4 ff     ..      ; call OSBYTE
    cpy threshold_lo                                                  ; 0a69: cc fd 0a    ...      ; past the low threshold?
    bcc read_done                                                     ; 0a6c: 90 25       .%       ; no -> not active
    bcs active                                                        ; 0a6e: b0 1e       ..       ; yes -> active
; &0a70 referenced 1 time by &0a62
.test_high_threshold
    lda #&80                                                          ; 0a70: a9 80       ..       ; OSBYTE &80: read ADC channel X...
    jsr osbyte                                                        ; 0a72: 20 f4 ff     ..      ; call OSBYTE
    cpy threshold_hi                                                  ; 0a75: cc fe 0a    ...      ; past the high threshold?
    bcc active                                                        ; 0a78: 90 14       ..       ; no -> active
    bcs read_done                                                     ; 0a7a: b0 17       ..       ; yes -> not active
; &0a7c referenced 1 time by &0a5e
.test_button
    and #3                                                            ; 0a7c: 29 03       ).       ; fire-button mask (low 2 bits)...
    sta button_mask                                                   ; 0a7e: 8d 97 0a    ...      ; ...saved
    lda #&80                                                          ; 0a81: a9 80       ..       ; OSBYTE &80: read ADC channel X...
    jsr osbyte                                                        ; 0a83: 20 f4 ff     ..      ; call OSBYTE
    txa                                                               ; 0a86: 8a          .        ; the returned button bits...
    and button_mask                                                   ; 0a87: 2d 97 0a    -..      ; ...AND the mask
    beq read_done                                                     ; 0a8a: f0 07       ..       ; none set -> not active
    bne active                                                        ; 0a8c: d0 00       ..       ; set -> active
; &0a8e referenced 3 times by &0a6e, &0a78, &0a8c
.active
    lda #&ff                                                          ; 0a8e: a9 ff       ..       ; Flag a hit...
    sta result_flag                                                   ; 0a90: 8d 98 0a    ...      ; ...in result_flag
; &0a93 referenced 3 times by &0a6c, &0a7a, &0a8a
.read_done
    pla                                                               ; 0a93: 68          h        ; Restore Y...
    tay                                                               ; 0a94: a8          .        ; store it
    pla                                                               ; 0a95: 68          h        ; Restore A
    rts                                                               ; 0a96: 60          `        ; Done
; &0a97 referenced 2 times by &0a7e, &0a87
.button_mask
    equb &ea                                                          ; 0a97: ea          .        ; Scratch: fire-button mask (&EA at rest)
; &0a98 referenced 3 times by &0a18, &0a2d, &0a90
.result_flag
    equb &ea                                                          ; 0a98: ea          .        ; Result byte (&EA at rest): the handler zeroes it, then sets it to &FF if a mapped input reads active
; Unused
.unused_a
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 0a99: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00        ; 0aa5: 00 00 00... ......
; 2-byte entries <INKEY key, input descriptor>. The key byte is 0 here; the BASIC (PROCASSEM, lines 1780-1830) pokes each with the user's chosen INKEY value. The fixed descriptor decodes as:
; &0ab0 used as index base 3 times by &0a1b, &0a4f, &0a59
.joystick_map
    equb &00, &10                                                     ; 0ab0: 00 10       ..       ; joystick axis: ADC channel 1, high threshold
    equb &00, &11                                                     ; 0ab2: 00 11       ..       ; joystick axis: ADC channel 1, low threshold
    equb &00, &20                                                     ; 0ab4: 00 20       .        ; joystick axis: ADC channel 2, high threshold
    equb &00, &21                                                     ; 0ab6: 00 21       .!       ; joystick axis: ADC channel 2, low threshold
    equb &00, &30                                                     ; 0ab8: 00 30       .0       ; joystick axis: ADC channel 3, high threshold
    equb &00, &31                                                     ; 0aba: 00 31       .1       ; joystick axis: ADC channel 3, low threshold
    equb &00, &40                                                     ; 0abc: 00 40       .@       ; joystick axis: ADC channel 4, high threshold
    equb &00, &41                                                     ; 0abe: 00 41       .A       ; joystick axis: ADC channel 4, low threshold
    equb &00, &01                                                     ; 0ac0: 00 01       ..       ; fire button: ADVAL(0), bit mask &1
    equb &00, &01                                                     ; 0ac2: 00 01       ..       ; fire button: ADVAL(0), bit mask &1
    equb &00, &02                                                     ; 0ac4: 00 02       ..       ; fire button: ADVAL(0), bit mask &2
    equb &00, &02                                                     ; 0ac6: 00 02       ..       ; fire button: ADVAL(0), bit mask &2
    equb &00, &61                                                     ; 0ac8: 00 61       .a       ; keypad cell &61 (inert in this analogue-only variant)
    equb &00, &32                                                     ; 0aca: 00 32       .2       ; keypad cell &32 (inert in this analogue-only variant)
    equb &00, &52                                                     ; 0acc: 00 52       .R       ; keypad cell &52 (inert in this analogue-only variant)
    equb &00, &62                                                     ; 0ace: 00 62       .b       ; keypad cell &62 (inert in this analogue-only variant)
    equb &00, &34                                                     ; 0ad0: 00 34       .4       ; keypad cell &34 (inert in this analogue-only variant)
    equb &00, &54                                                     ; 0ad2: 00 54       .T       ; keypad cell &54 (inert in this analogue-only variant)
    equb &00, &64                                                     ; 0ad4: 00 64       .d       ; keypad cell &64 (inert in this analogue-only variant)
    equb &00, &38                                                     ; 0ad6: 00 38       .8       ; keypad cell &38 (inert in this analogue-only variant)
    equb &00, &58                                                     ; 0ad8: 00 58       .X       ; keypad cell &58 (inert in this analogue-only variant)
    equb &00, &68                                                     ; 0ada: 00 68       .h       ; keypad cell &68 (inert in this analogue-only variant)
    equb &00, &d1                                                     ; 0adc: 00 d1       ..       ; keypad cell &D1 (inert in this analogue-only variant)
    equb &00, &d1                                                     ; 0ade: 00 d1       ..       ; keypad cell &D1 (inert in this analogue-only variant)
    equb &00, &d1                                                     ; 0ae0: 00 d1       ..       ; keypad cell &D1 (inert in this analogue-only variant)
    equb &00, &b1                                                     ; 0ae2: 00 b1       ..       ; keypad cell &B1 (inert in this analogue-only variant)
    equb &00, &e1                                                     ; 0ae4: 00 e1       ..       ; keypad cell &E1 (inert in this analogue-only variant)
    equb &00, &b2                                                     ; 0ae6: 00 b2       ..       ; keypad cell &B2 (inert in this analogue-only variant)
    equb &00, &d2                                                     ; 0ae8: 00 d2       ..       ; keypad cell &D2 (inert in this analogue-only variant)
    equb &00, &e2                                                     ; 0aea: 00 e2       ..       ; keypad cell &E2 (inert in this analogue-only variant)
    equb &00, &b4                                                     ; 0aec: 00 b4       ..       ; keypad cell &B4 (inert in this analogue-only variant)
    equb &00, &d4                                                     ; 0aee: 00 d4       ..       ; keypad cell &D4 (inert in this analogue-only variant)
    equb &00, &e4                                                     ; 0af0: 00 e4       ..       ; keypad cell &E4 (inert in this analogue-only variant)
    equb &00, &b8                                                     ; 0af2: 00 b8       ..       ; keypad cell &B8 (inert in this analogue-only variant)
    equb &00, &d8                                                     ; 0af4: 00 d8       ..       ; keypad cell &D8 (inert in this analogue-only variant)
    equb &00, &e8                                                     ; 0af6: 00 e8       ..       ; keypad cell &E8 (inert in this analogue-only variant)
    equb &00, &00                                                     ; 0af8: 00 00       ..       ; end-of-map marker
; RTS placeholder; the BASIC (line 1840) patches this to JMP <previous BYTEV> so non-INKEY OSBYTEs are chained.
; &0afa referenced 1 time by &0a3d
.chain_to_old_bytev
    equb &60, &00, &00                                                ; 0afa: 60 00 00    `..   
; &0afd referenced 1 time by &0a69
.threshold_lo
    equb &00                                                          ; 0afd: 00          .        ; Low sensitivity threshold (BASIC line 1850: SL%)
; &0afe referenced 1 time by &0a75
.threshold_hi
    equb &00                                                          ; 0afe: 00          .        ; High sensitivity threshold (BASIC line 1850: SH%)
.unused_a_end
    equb &00                                                          ; 0aff: 00          .        ; Unused
.dasmos_end

save dasmos_start, dasmos_end

; Label references by decreasing frequency:
;     active:               3
;     joystick_map:         3
;     osbyte:               3
;     read_done:            3
;     result_flag:          3
;     button_mask:          2
;     bytev:                1
;     bytev_hi:             1
;     chain:                1
;     chain_to_old_bytev:   1
;     not_pressed:          1
;     read_joystick:        1
;     scan_map:             1
;     scan_more:            1
;     scan_next:            1
;     skip_to_directions:   1
;     test_button:          1
;     test_high_threshold:  1
;     threshold_hi:         1
;     threshold_lo:         1

; Stats:
;     Total size (Code + Data) = 256 bytes
;     Code                     = 151 bytes (59%)
;     Data                     = 105 bytes (41%)
;
;     Number of instructions   = 89
;     Number of data bytes     = 105 bytes
;     Number of data words     = 0 bytes
;     Number of string bytes   = 0 bytes
;     Number of strings        = 0
