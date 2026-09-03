; Constants
osbyte_inkey                         = &81
osbyte_read_adc_or_get_buffer_status = &80

; Memory locations
bytev            = &020a
; &020a referenced 1 time by &0a03
bytev_hi         = &020b
; &020b referenced 1 time by &0a08
user_via_orb_irb = &fe60
; &fe60 referenced 2 times by &0a84, &0a87
user_via_ddrb    = &fe62
; &fe62 referenced 1 time by &0a7b
osbyte           = &fff4
; &fff4 referenced 2 times by &0a55, &0a61


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
; BYTEV handler: map the joystick and keypad to INKEY
;
; As variant A, but joystick_map entries >= &10 test the Delta 14B keypad matrix through
; the User VIA instead of an analogue channel.
.osbyte_intercept
    cmp #osbyte_inkey                                                 ; 0a0d: c9 81       ..       ; Only intercept OSBYTE &81 (INKEY / read key)
    bne chain                                                         ; 0a0f: d0 28       .(       ; other reason codes -> chain to the previous handler
    pha                                                               ; 0a11: 48          H        ; Preserve A (reason code)...
    tya                                                               ; 0a12: 98          .        ; Preserve Y (INKEY high byte)...
    pha                                                               ; 0a13: 48          H        ; on the stack
    txa                                                               ; 0a14: 8a          .        ; A := X = the INKEY key number being tested
    pha                                                               ; 0a15: 48          H        ; ...(X also preserved)
    ldy #0                                                            ; 0a16: a0 00       ..       ; No match yet...
    sty result_flag                                                   ; 0a18: 8c 9d 0a    ...      ; ...clear the result flag
; &0a1b referenced 1 time by &0a27
.scan_map
    cmp joystick_map,y                                                ; 0a1b: d9 b0 0a    ...      ; Does the tested key match this map entry?
    bne scan_next                                                     ; 0a1e: d0 03       ..       ; no -> skip it
    jsr read_input                                                    ; 0a20: 20 3c 0a     <.      ; yes -> read the mapped input for it
; &0a23 referenced 1 time by &0a1e
.scan_next
    iny                                                               ; 0a23: c8          .        ; Step over the 2-byte entry...
    iny                                                               ; 0a24: c8          .        ; twice
    cpy #&48 ; 'H'                                                    ; 0a25: c0 48       .H       ; end of the map?
    bne scan_map                                                      ; 0a27: d0 f2       ..       ; no -> keep scanning
    lda result_flag                                                   ; 0a29: ad 9d 0a    ...      ; Did any mapped input read as active?
    beq not_pressed                                                   ; 0a2c: f0 06       ..       ; no -> return the normal INKEY result
    tax                                                               ; 0a2e: aa          .        ; yes: return "key pressed" (X=Y=&FF)...
    tay                                                               ; 0a2f: a8          .        ; X and Y
    pla                                                               ; 0a30: 68          h        ; drop the saved X...
    pla                                                               ; 0a31: 68          h        ; ...Y...
    pla                                                               ; 0a32: 68          h        ; ...A
    rts                                                               ; 0a33: 60          `        ; and return, claiming the OSBYTE
; &0a34 referenced 1 time by &0a2c
.not_pressed
    pla                                                               ; 0a34: 68          h        ; Restore X...
    tax                                                               ; 0a35: aa          .        ; into X
    pla                                                               ; 0a36: 68          h        ; Restore Y...
    tay                                                               ; 0a37: a8          .        ; into Y
    pla                                                               ; 0a38: 68          h        ; Restore A
; &0a39 referenced 1 time by &0a0f
.chain
    jmp chain_to_old_bytev                                            ; 0a39: 4c fa 0a    L..      ; Pass the call to the previous BYTEV (chain slot below)
; ***************************************************************************************
; Test one joystick or keypad input
;
; For the matched entry: entries below &10 read an analogue channel (OSBYTE &80 / ADVAL)
; against the thresholds; entries >= &10 strobe a keypad column through User VIA port B
; and test a row bit. A hit sets result_flag.
; &0a3c referenced 1 time by &0a20
.read_input
    pha                                                               ; 0a3c: 48          H        ; Preserve A...
    tya                                                               ; 0a3d: 98          .        ; Preserve Y...
    pha                                                               ; 0a3e: 48          H        ; on the stack
    cmp #&10                                                          ; 0a3f: c9 10       ..       ; Analogue entry (< &10) or keypad entry?
    bpl test_keypad                                                   ; 0a41: 10 28       .(       ; > = &10 -> the keypad path
    iny                                                               ; 0a43: c8          .        ; Point at the entry parameter
    lda joystick_map,y                                                ; 0a44: b9 b0 0a    ...      ; ADC channel in the top nibble...
    lsr a                                                             ; 0a47: 4a          J        ; ...shift it down...
    lsr a                                                             ; 0a48: 4a          J        ; ...shift it down...
    lsr a                                                             ; 0a49: 4a          J        ; ...shift it down...
    lsr a                                                             ; 0a4a: 4a          J        ; ...shift it down...
    tax                                                               ; 0a4b: aa          .        ; ...into X for OSBYTE &80
    lda joystick_map,y                                                ; 0a4c: b9 b0 0a    ...      ; reload the parameter
    and #1                                                            ; 0a4f: 29 01       ).       ; low bit picks which threshold (push vs pull)
    beq test_high_threshold                                           ; 0a51: f0 0c       ..       ; else test the high threshold
    lda #osbyte_read_adc_or_get_buffer_status                         ; 0a53: a9 80       ..       ; OSBYTE &80: read ADC channel X (ADVAL, Y=high byte)...
    jsr osbyte                                                        ; 0a55: 20 f4 ff     ..      ; call OSBYTE  Read ADC channel X or buffer status
    cpy threshold_lo                                                  ; 0a58: cc fd 0a    ...      ; past the low threshold?
    bcc read_done                                                     ; 0a5b: 90 3a       .:       ; no -> not active
    bcs active                                                        ; 0a5d: b0 33       .3       ; yes -> active
; &0a5f referenced 1 time by &0a51
.test_high_threshold
    lda #osbyte_read_adc_or_get_buffer_status                         ; 0a5f: a9 80       ..       ; OSBYTE &80: read ADC channel X...
    jsr osbyte                                                        ; 0a61: 20 f4 ff     ..      ; call OSBYTE  Read ADC channel X or buffer status
    cpy threshold_hi                                                  ; 0a64: cc fe 0a    ...      ; past the high threshold?
    bcc active                                                        ; 0a67: 90 29       .)       ; no -> active
    bcs read_done                                                     ; 0a69: b0 2c       .,       ; yes -> not active
; &0a6b referenced 1 time by &0a41
.test_keypad
    iny                                                               ; 0a6b: c8          .        ; Point at the entry parameter
    lda joystick_map,y                                                ; 0a6c: b9 b0 0a    ...      ; top nibble = the column strobe...
    and #&f0                                                          ; 0a6f: 29 f0       ).       ; mask the top nibble
    sta col_strobe                                                    ; 0a71: 8d 9c 0a    ...      ; ...saved
    lda joystick_map,y                                                ; 0a74: b9 b0 0a    ...      ; low nibble = the row bit mask...
    and #&0f                                                          ; 0a77: 29 0f       ).       ; mask the low nibble
    ldy #&f0                                                          ; 0a79: a0 f0       ..       ; DDRB = &F0: strobes out, rows in...
    sty user_via_ddrb                                                 ; 0a7b: 8c 62 fe    .b.      ; set it
    sta row_mask                                                      ; 0a7e: 8d 9b 0a    ...      ; save the row mask
    ldy col_strobe                                                    ; 0a81: ac 9c 0a    ...      ; Drive the column strobe...
    sty user_via_orb_irb                                              ; 0a84: 8c 60 fe    .`.      ; ...onto port B
    ldy user_via_orb_irb                                              ; 0a87: ac 60 fe    .`.      ; Read the rows back...
    tya                                                               ; 0a8a: 98          .        ; into A
    and row_mask                                                      ; 0a8b: 2d 9b 0a    -..      ; ...and mask this row bit
    beq active                                                        ; 0a8e: f0 02       ..       ; low (pressed) -> not-active path...
    bne read_done                                                     ; 0a90: d0 05       ..       ; high -> active
; &0a92 referenced 3 times by &0a5d, &0a67, &0a8e
.active
    lda #&ff                                                          ; 0a92: a9 ff       ..       ; Flag a hit...
    sta result_flag                                                   ; 0a94: 8d 9d 0a    ...      ; ...in result_flag
; &0a97 referenced 3 times by &0a5b, &0a69, &0a90
.read_done
    pla                                                               ; 0a97: 68          h        ; Restore Y...
    tay                                                               ; 0a98: a8          .        ; into Y
    pla                                                               ; 0a99: 68          h        ; Restore A
    rts                                                               ; 0a9a: 60          `        ; Done
; &0a9b referenced 2 times by &0a7e, &0a8b
.row_mask
    equb &ea                                                          ; 0a9b: ea          .        ; Scratch: keypad row bit mask (&EA at rest)
; &0a9c referenced 2 times by &0a71, &0a81
.col_strobe
    equb &ea                                                          ; 0a9c: ea          .        ; Scratch: keypad column strobe (&EA at rest)
; &0a9d referenced 3 times by &0a18, &0a29, &0a94
.result_flag
    equb &ea                                                          ; 0a9d: ea          .        ; Result byte (&EA at rest): the handler zeroes it, then sets it to &FF if a mapped input reads active
; Unused
.unused_b
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 0a9e: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00                                 ; 0aaa: 00 00 00... ......
; 2-byte entries <INKEY key, input descriptor>. The key byte is 0 here; the BASIC (PROCASSEM, lines 1780-1830) pokes each with the user's chosen INKEY value. The fixed descriptor decodes as:
; &0ab0 used as index base 5 times by &0a1b, &0a44, &0a4c, &0a6c, &0a74
.joystick_map
    equb &00, &10                                                     ; 0ab0: 00 10       ..       ; joystick axis: ADC channel 1, high threshold
    equb &00, &11                                                     ; 0ab2: 00 11       ..       ; joystick axis: ADC channel 1, low threshold
    equb &00, &20                                                     ; 0ab4: 00 20       .        ; joystick axis: ADC channel 2, high threshold
    equb &00, &21                                                     ; 0ab6: 00 21       .!       ; joystick axis: ADC channel 2, low threshold
    equb &00, &30                                                     ; 0ab8: 00 30       .0       ; joystick axis: ADC channel 3, high threshold
    equb &00, &31                                                     ; 0aba: 00 31       .1       ; joystick axis: ADC channel 3, low threshold
    equb &00, &40                                                     ; 0abc: 00 40       .@       ; joystick axis: ADC channel 4, high threshold
    equb &00, &41                                                     ; 0abe: 00 41       .A       ; joystick axis: ADC channel 4, low threshold
    equb &00, &51                                                     ; 0ac0: 00 51       .Q       ; keypad: strobe column &50, test row bit &1
    equb &00, &51                                                     ; 0ac2: 00 51       .Q       ; keypad: strobe column &50, test row bit &1
    equb &00, &51                                                     ; 0ac4: 00 51       .Q       ; keypad: strobe column &50, test row bit &1
    equb &00, &31                                                     ; 0ac6: 00 31       .1       ; keypad: strobe column &30, test row bit &1
    equb &00, &61                                                     ; 0ac8: 00 61       .a       ; keypad: strobe column &60, test row bit &1
    equb &00, &32                                                     ; 0aca: 00 32       .2       ; keypad: strobe column &30, test row bit &2
    equb &00, &52                                                     ; 0acc: 00 52       .R       ; keypad: strobe column &50, test row bit &2
    equb &00, &62                                                     ; 0ace: 00 62       .b       ; keypad: strobe column &60, test row bit &2
    equb &00, &34                                                     ; 0ad0: 00 34       .4       ; keypad: strobe column &30, test row bit &4
    equb &00, &54                                                     ; 0ad2: 00 54       .T       ; keypad: strobe column &50, test row bit &4
    equb &00, &64                                                     ; 0ad4: 00 64       .d       ; keypad: strobe column &60, test row bit &4
    equb &00, &38                                                     ; 0ad6: 00 38       .8       ; keypad: strobe column &30, test row bit &8
    equb &00, &58                                                     ; 0ad8: 00 58       .X       ; keypad: strobe column &50, test row bit &8
    equb &00, &68                                                     ; 0ada: 00 68       .h       ; keypad: strobe column &60, test row bit &8
    equb &00, &d1                                                     ; 0adc: 00 d1       ..       ; keypad: strobe column &D0, test row bit &1
    equb &00, &d1                                                     ; 0ade: 00 d1       ..       ; keypad: strobe column &D0, test row bit &1
    equb &00, &d1                                                     ; 0ae0: 00 d1       ..       ; keypad: strobe column &D0, test row bit &1
    equb &00, &b1                                                     ; 0ae2: 00 b1       ..       ; keypad: strobe column &B0, test row bit &1
    equb &00, &e1                                                     ; 0ae4: 00 e1       ..       ; keypad: strobe column &E0, test row bit &1
    equb &00, &b2                                                     ; 0ae6: 00 b2       ..       ; keypad: strobe column &B0, test row bit &2
    equb &00, &d2                                                     ; 0ae8: 00 d2       ..       ; keypad: strobe column &D0, test row bit &2
    equb &00, &e2                                                     ; 0aea: 00 e2       ..       ; keypad: strobe column &E0, test row bit &2
    equb &00, &b4                                                     ; 0aec: 00 b4       ..       ; keypad: strobe column &B0, test row bit &4
    equb &00, &d4                                                     ; 0aee: 00 d4       ..       ; keypad: strobe column &D0, test row bit &4
    equb &00, &e4                                                     ; 0af0: 00 e4       ..       ; keypad: strobe column &E0, test row bit &4
    equb &00, &b8                                                     ; 0af2: 00 b8       ..       ; keypad: strobe column &B0, test row bit &8
    equb &00, &d8                                                     ; 0af4: 00 d8       ..       ; keypad: strobe column &D0, test row bit &8
    equb &00, &e8                                                     ; 0af6: 00 e8       ..       ; keypad: strobe column &E0, test row bit &8
    equb &00, &00                                                     ; 0af8: 00 00       ..       ; end-of-map marker
; RTS placeholder; the BASIC (line 1840) patches this to JMP <previous BYTEV> so non-INKEY OSBYTEs are chained.
; &0afa referenced 1 time by &0a39
.chain_to_old_bytev
    equb &60, &00, &00                                                ; 0afa: 60 00 00    `..   
; &0afd referenced 1 time by &0a58
.threshold_lo
    equb &00                                                          ; 0afd: 00          .        ; Low-threshold comparison value; BASIC line 1850 pokes SH% here
; &0afe referenced 1 time by &0a64
.threshold_hi
    equb &00                                                          ; 0afe: 00          .        ; High-threshold comparison value; BASIC line 1850 pokes SL% here
.unused_b_end
    equb &00                                                          ; 0aff: 00          .        ; Unused
.dasmos_end

save dasmos_start, dasmos_end

; Label references by decreasing frequency:
;     joystick_map:         5
;     active:               3
;     read_done:            3
;     result_flag:          3
;     col_strobe:           2
;     osbyte:               2
;     row_mask:             2
;     user_via_orb_irb:     2
;     bytev:                1
;     bytev + 1:            1
;     bytev_hi:             1
;     chain:                1
;     chain_to_old_bytev:   1
;     not_pressed:          1
;     read_input:           1
;     scan_map:             1
;     scan_next:            1
;     test_high_threshold:  1
;     test_keypad:          1
;     threshold_hi:         1
;     threshold_lo:         1
;     user_via_ddrb:        1

; Stats:
;     Total size (Code + Data) = 256 bytes
;     Code                     = 155 bytes (61%)
;     Data                     = 101 bytes (39%)
;
;     Number of instructions   = 84
;     Number of data bytes     = 101 bytes
;     Number of data words     = 0 bytes
;     Number of string bytes   = 0 bytes
;     Number of strings        = 0
