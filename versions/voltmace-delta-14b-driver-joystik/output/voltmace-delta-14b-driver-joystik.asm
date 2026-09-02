; Memory locations
decode_ptr     = &80
; &80 referenced 5 times by &191d, &1929, &1931, &1937, &1946
decode_ptr_hi  = &81
; &81 referenced 4 times by &1922, &192f, &193c, &194b
autorun_index  = &023c
; &023c referenced 4 times by &197e, &1989, &198c, &1993
kbd_buffer     = &0300
; &0300 used as index base 1 time by &1986
os_signature   = &e8aa
; &e8aa referenced 1 time by &1950
os_signature_1 = &e8ab
; &e8ab referenced 1 time by &1958
os_signature_2 = &e8ac
; &e8ac referenced 1 time by &1960
osbyte         = &fff4
; &fff4 referenced 2 times by &199f, &19b2


    org &1900

.dasmos_start
; Decoy stub BASIC line (&0D, line 13, RTS bytes) so a naive *LOAD/LIST at PAGE sees junk, not the loader
.decoy
    equb &0d, &00, &0d, &60, &60, &60, &60, &60, &60                  ; 1900: 0d 00 0d... ......
; ***************************************************************************************
; *RUN entry: decrypt and auto-run
;
; The DFS execution address. Decrypts the drivers and BASIC in place, repairs the BASIC's
; first line, then queues PAGE=&1C00 / OLD / RUN so the now-plain BASIC configuration
; program starts.
.main
    pha                                                               ; 1909: 48          H        ; Preserve A
    txa                                                               ; 190a: 8a          .        ; Preserve X...
    pha                                                               ; 190b: 48          H        ; ...on the stack
    tya                                                               ; 190c: 98          .        ; Preserve Y...
    pha                                                               ; 190d: 48          H        ; ...on the stack
    jsr decode_basic                                                  ; 190e: 20 1d 19     ..      ; Decrypt the drivers and BASIC in place
    jsr patch_header                                                  ; 1911: 20 76 19     v.      ; Repair the BASIC's first-line length byte
    jsr os_dependent_setup                                            ; 1914: 20 4e 19     N.      ; Queue the auto-run commands (OS-dependent)
    pla                                                               ; 1917: 68          h        ; Restore Y...
    tay                                                               ; 1918: a8          .        ; ...
    pla                                                               ; 1919: 68          h        ; Restore X...
    tax                                                               ; 191a: aa          .        ; ...
    pla                                                               ; 191b: 68          h        ; Restore A
    rts                                                               ; 191c: 60          `        ; Return to the MOS; the queued commands then run the BASIC
; ***************************************************************************************
; Decrypt the drivers and BASIC
;
; Rotate every byte of &1A00-&4AFF left one bit (the inverse of the ROL-1 storage
; protection), in place. That covers both driver variants (&1A00, &1B00) and the
; tokenised BASIC from PAGE=&1C00; the loop stops at page &4B, leaving the BASIC's raw
; tail untouched.
; &191d referenced 1 time by &190e
.decode_basic
    lda decode_ptr                                                    ; 191d: a5 80       ..       ; Save the caller decode_ptr low byte...
    sta decode_ptr_save                                               ; 191f: 8d 74 19    .t.      ; ...
    lda decode_ptr_hi                                                 ; 1922: a5 81       ..       ; ...and high byte...
    sta decode_ptr_save_hi                                            ; 1924: 8d 75 19    .u.      ; ...at decode_ptr_save
    ldx #0                                                            ; 1927: a2 00       ..       ; Point decode_ptr at &1A00: low byte 0...
    stx decode_ptr                                                    ; 1929: 86 80       ..       ; ...
    ldx #&1a                                                          ; 192b: a2 1a       ..       ; ...high byte &1A...
    ldy #0                                                            ; 192d: a0 00       ..       ; byte index 0
; &192f referenced 1 time by &1941
.decode_next_page
    stx decode_ptr_hi                                                 ; 192f: 86 81       ..       ; Set the page being decrypted
; &1931 referenced 1 time by &193a
.decode_next_byte
    lda (decode_ptr),y                                                ; 1931: b1 80       ..       ; Read an encrypted byte...
    clc                                                               ; 1933: 18          .        ; clear carry for the rotate
    asl a                                                             ; 1934: 0a          .        ; ...rotate it left one bit (undo the ROL-1 protection)...
    adc #0                                                            ; 1935: 69 00       i.       ; ...carrying bit 7 into bit 0...
    sta (decode_ptr),y                                                ; 1937: 91 80       ..       ; ...and store it back
    iny                                                               ; 1939: c8          .        ; Next byte...
    bne decode_next_byte                                              ; 193a: d0 f5       ..       ; ...to the end of the page
    ldx decode_ptr_hi                                                 ; 193c: a6 81       ..       ; Next page...
    inx                                                               ; 193e: e8          .        ; ...
    cpx #&4b ; 'K'                                                    ; 193f: e0 4b       .K       ; ...until page &4B (the BASIC raw tail is left alone)
    bne decode_next_page                                              ; 1941: d0 ec       ..       ; ...
    lda decode_ptr_save                                               ; 1943: ad 74 19    .t.      ; Restore the caller decode_ptr...
    sta decode_ptr                                                    ; 1946: 85 80       ..       ; ...
    lda decode_ptr_save_hi                                            ; 1948: ad 75 19    .u.      ; ...
    sta decode_ptr_hi                                                 ; 194b: 85 81       ..       ; ...
    rts                                                               ; 194d: 60          `        ; Done
; ***************************************************************************************
; OS-version-dependent setup
;
; Reads the three-byte "OS " ROM signature to pick how the auto-run commands are queued.
; &194e referenced 1 time by &1914
.os_dependent_setup
    ldy #0                                                            ; 194e: a0 00       ..       ; Count matching signature bytes in Y
    lda os_signature                                                  ; 1950: ad aa e8    ...      ; First OS ROM byte...
    cmp #&4f ; 'O'                                                    ; 1953: c9 4f       .O       ; ...'O'?
    bne os_check_1                                                    ; 1955: d0 01       ..       ; ...
    iny                                                               ; 1957: c8          .        ; match: bump the count
; &1958 referenced 1 time by &1955
.os_check_1
    lda os_signature_1                                                ; 1958: ad ab e8    ...      ; Second OS ROM byte...
    cmp #&53 ; 'S'                                                    ; 195b: c9 53       .S       ; ...'S'?
    bne os_check_2                                                    ; 195d: d0 01       ..       ; ...
    iny                                                               ; 195f: c8          .        ; match: bump the count
; &1960 referenced 1 time by &195d
.os_check_2
    lda os_signature_2                                                ; 1960: ad ac e8    ...      ; Third OS ROM byte...
    cmp #&20 ; ' '                                                    ; 1963: c9 20       .        ; ...' '?
    bne os_check_done                                                 ; 1965: d0 01       ..       ; ...
    iny                                                               ; 1967: c8          .        ; match: bump the count
; &1968 referenced 1 time by &1965
.os_check_done
    cpy #3                                                            ; 1968: c0 03       ..       ; All three bytes matched "OS "?
    beq use_direct_poke                                               ; 196a: f0 04       ..       ; yes -> poke the buffer directly
    jsr setup_keys                                                    ; 196c: 20 9b 19     ..      ; no -> insert via OSBYTE
    rts                                                               ; 196f: 60          `        ; Done
; &1970 referenced 1 time by &196a
.use_direct_poke
    jsr queue_autorun                                                 ; 1970: 20 7c 19     |.      ; Queue by poking the keyboard buffer
    rts                                                               ; 1973: 60          `        ; Done
; &1974 referenced 2 times by &191f, &1943
.decode_ptr_save
; &1975 referenced 2 times by &1924, &1948
decode_ptr_save_hi = decode_ptr_save+1
    equw &0000                                                        ; 1974: 00 00       ..       ; Scratch: caller's decode_ptr saved across decode_basic
; ***************************************************************************************
; Repair the BASIC program's first line
;
; Write &17 (23) into basic_line10_len, the length byte of the line-10 REM at PAGE=&1C00,
; which is stored as 0 by the protection.
; &1976 referenced 1 time by &1911
.patch_header
    lda #&17                                                          ; 1976: a9 17       ..       ; The first BASIC line is 23 bytes long...
    sta basic_line10_len                                              ; 1978: 8d 03 1c    ...      ; ...restore its length byte (stored as 0 by the protection)
    rts                                                               ; 197b: 60          `        ; Done
; ***************************************************************************************
; Queue the auto-run commands (direct poke)
;
; Copy autorun_commands into the MOS keyboard buffer so the OS reads them as typed.
; autorun_index wraps into the 32-byte buffer at &03E0-&03FF.
; &197c referenced 1 time by &1970
.queue_autorun
    ldy #0                                                            ; 197c: a0 00       ..       ; Start at the first command byte
; &197e referenced 1 time by &1997
.queue_next_byte
    ldx autorun_index                                                 ; 197e: ae 3c 02    .<.      ; Current buffer fill position...
    lda autorun_commands,y                                            ; 1981: b9 bf 19    ...      ; read a command byte...
    beq queue_done                                                    ; 1984: f0 14       ..       ; ...&00 terminates
    sta kbd_buffer,x                                                  ; 1986: 9d 00 03    ...      ; Poke it into the keyboard buffer
    inc autorun_index                                                 ; 1989: ee 3c 02    .<.      ; Advance the fill position...
    lda autorun_index                                                 ; 198c: ad 3c 02    .<.      ; ...
    bne queue_advance                                                 ; 198f: d0 05       ..       ; ...
    lda #&e0                                                          ; 1991: a9 e0       ..       ; ...wrapping back to &E0 (buffer at &03E0)...
    sta autorun_index                                                 ; 1993: 8d 3c 02    .<.      ; ...
; &1996 referenced 1 time by &198f
.queue_advance
    iny                                                               ; 1996: c8          .        ; Next command byte
    jmp queue_next_byte                                               ; 1997: 4c 7e 19    L~.      ; ...
; &199a referenced 1 time by &1984
.queue_done
    rts                                                               ; 199a: 60          `        ; Done
; ***************************************************************************************
; Queue the auto-run commands (OSBYTE path)
;
; The non-"OS "-signature variant of queue_autorun: set the BREAK/ESCAPE behaviour, then
; insert each autorun_commands byte with OSBYTE &8A.
; &199b referenced 1 time by &196c
.setup_keys
    lda #&c8                                                          ; 199b: a9 c8       ..       ; OSBYTE 200: set the BREAK/ESCAPE behaviour...
    ldx #3                                                            ; 199d: a2 03       ..       ; ...
    jsr osbyte                                                        ; 199f: 20 f4 ff     ..      ; call OSBYTE
    ldx #0                                                            ; 19a2: a2 00       ..       ; Start at the first command byte
; &19a4 referenced 1 time by &19ba
.insert_next_key
    lda autorun_commands,x                                            ; 19a4: bd bf 19    ...      ; Read a command byte...
    beq setup_keys_done                                               ; 19a7: f0 14       ..       ; ...&00 terminates
    tay                                                               ; 19a9: a8          .        ; The character to insert
    txa                                                               ; 19aa: 8a          .        ; Save the loop index...
    sta setup_key_index                                               ; 19ab: 8d be 19    ...      ; ...
    ldx #0                                                            ; 19ae: a2 00       ..       ; OSBYTE &8A: insert Y into buffer 0 (keyboard)...
    lda #&8a                                                          ; 19b0: a9 8a       ..       ; A = &8A
    jsr osbyte                                                        ; 19b2: 20 f4 ff     ..      ; call OSBYTE
    lda setup_key_index                                               ; 19b5: ad be 19    ...      ; Restore the loop index...
    tax                                                               ; 19b8: aa          .        ; ...
    inx                                                               ; 19b9: e8          .        ; Next command byte
    jmp insert_next_key                                               ; 19ba: 4c a4 19    L..      ; ...
; &19bd referenced 1 time by &19a7
.setup_keys_done
    rts                                                               ; 19bd: 60          `        ; Done
; &19be referenced 2 times by &19ab, &19b5
.setup_key_index
    equb &ea                                                          ; 19be: ea          .        ; Scratch: saved loop index (&EA at rest)
; &19bf used as index base 2 times by &1981, &19a4
.autorun_commands
    equb &15, &0d                                                     ; 19bf: 15 0d       ..       ; CTRL-U + CR: clear the input line
    equs "PA.=&1C00"                                                  ; 19c1: 50 41 2e... PA....   ; set PAGE to &1C00, where the BASIC lives
    equb &0d                                                          ; 19ca: 0d          .        ; submit
    equs "OLD"                                                        ; 19cb: 4f 4c 44    OLD      ; reinstate the decoded program (OLD)
    equb &0d                                                          ; 19ce: 0d          .        ; submit
    equs "RUN"                                                        ; 19cf: 52 55 4e    RUN      ; run it (RUN)
    equb &0d, &00                                                     ; 19d2: 0d 00       ..       ; submit; the &00 then stops the queue copy
; Unused bytes after the command list, up to the driver at &1A00; referenced by nothing and inert.
.loader_tail
    equb &0d, &54, &67, &42, &cc, &6d, &f6, &b0, &c0, &ff, &38, &25   ; 19d4: 0d 54 67... .Tg...
    equb &4d, &05, &55, &06, &b7, &84, &20, &d6, &88, &b0, &40, &bd   ; 19e0: 4d 05 55... M.U...
    equb &d3, &fa, &c8, &10, &f8, &f1, &eb, &44, &1b, &4c, &01, &63   ; 19ec: d3 fa c8... ......
    equb &f6, &50, &74, &21, &39, &71, &c0, &86                       ; 19f8: f6 50 74... .Pt...
; ROL-encoded: driver variant A (&1A00), driver variant B (&1B00), then the tokenised BASIC from PAGE=&1C00 (raw past &4B00). Drivers: see driver_a.asm/driver_b.asm; BASIC: basic/voltmace-delta-14b-driver-joystik.bas.
.encoded_region
; &1c03 referenced 1 time by &1978
basic_line10_len = encoded_region+515
    incbin "voltmace-delta-14b-driver-joystik-encoded.dat"            ; 1a00: 24 d4 86... $.....
; BBC BASIC's variable heap as it stood when the author saved the &1900-&4D00 image: variable-name/value records for the program globals (e.g. REV$="Rev 2.0", and LR%, R1%, EV$, LVL%, LVH%, S% ...). Not used by the loader; PAGE=&1C00 sits below it, so BASIC rebuilds its own variables on RUN.
.basic_variables
    equb &e5, &e5, &e5, &e5, &e5, &a1, &4c, &52, &25, &00, &00, &00   ; 4c93: e5 e5 e5... ......
    equb &00, &00, &e5, &00, &52, &31, &25, &00, &00, &00, &00, &00   ; 4c9f: 00 00 e5... ......
    equb &e5, &00, &45, &56, &24, &00, &b5, &4c, &07, &07, &52, &65   ; 4cab: e5 00 45... ..E...
    equb &76, &20, &32, &2e, &30, &c6, &4c, &56, &4c, &25, &00, &72   ; 4cb7: 76 20 32... v 2...
    equb &00, &00, &00, &d0, &4c, &56, &48, &25, &00, &e7, &00, &00   ; 4cc3: 00 00 00... ......
    equb &00, &e5, &00, &53, &25, &00, &01, &00, &00, &00, &e5, &00   ; 4ccf: 00 e5 00... ......
    equb &25, &28, &00, &03, &49, &00, &21, &00, &00, &00, &72, &00   ; 4cdb: 25 28 00... %(....
    equb &00, &00, &73, &00, &00, &00, &74, &00, &00, &00, &15, &00   ; 4ce7: 00 00 73... ..s...
    equb &00, &00, &75, &00, &00, &00, &76, &00, &00, &00, &17, &00   ; 4cf3: 00 00 75... ..u...
    equb &00                                                          ; 4cff: 00          .     
.dasmos_end

save dasmos_start, dasmos_end, &1909, &1900

; Label references by decreasing frequency:
;     decode_ptr:          5
;     autorun_index:       4
;     decode_ptr_hi:       4
;     autorun_commands:    2
;     decode_ptr_save:     2
;     decode_ptr_save_hi:  2
;     osbyte:              2
;     setup_key_index:     2
;     basic_line10_len:    1
;     decode_basic:        1
;     decode_next_byte:    1
;     decode_next_page:    1
;     insert_next_key:     1
;     kbd_buffer:          1
;     os_check_1:          1
;     os_check_2:          1
;     os_check_done:       1
;     os_dependent_setup:  1
;     os_signature:        1
;     os_signature_1:      1
;     os_signature_2:      1
;     patch_header:        1
;     queue_advance:       1
;     queue_autorun:       1
;     queue_done:          1
;     queue_next_byte:     1
;     setup_keys:          1
;     setup_keys_done:     1
;     use_direct_poke:     1

; Stats:
;     Total size (Code + Data) = 13312 bytes
;     Code                     = 179 bytes (1%)
;     Data                     = 13133 bytes (99%)
;
;     Number of instructions   = 91
;     Number of data bytes     = 169 bytes
;     Number of data words     = 2 bytes
;     Number of string bytes   = 15 bytes
;     Number of strings        = 3
;     Number of included bytes = 12947 bytes
;     Number of includes       = 1
