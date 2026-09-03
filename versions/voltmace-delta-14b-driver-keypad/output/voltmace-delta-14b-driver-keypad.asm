; Memory locations
copy_dst         = &70  ; Block-copy destination pointer used by the relocator.
; &70 referenced 3 times by &39bc, &39d8, &39ea
copy_dst_hi      = &71
; &71 referenced 3 times by &39c0, &39d0, &39df
copy_src         = &72  ; Block-copy source pointer used by the relocator.
; &72 referenced 3 times by &39c4, &39d6, &39e8
copy_src_hi      = &73
; &73 referenced 2 times by &39c8, &39dd
copy_rem         = &74  ; Leftover (part-page) byte count for the relocator.
; &74 referenced 2 times by &39b4, &39e4
copy_pages       = &75  ; Whole-page count for the relocator.
; &75 referenced 2 times by &39b8, &39cc
decode_ptr       = &80  ; ROL-decode cursor sweeping the encrypted BASIC in place.
; &80 referenced 5 times by &391d, &3929, &3931, &3937, &3946
decode_ptr_hi    = &81
; &81 referenced 4 times by &3922, &392f, &393c, &394b
evntv            = &0220  ; EVNTV, the event vector: the resident driver saves the old value and points it at its vsync-event handler.
; &0220 referenced 2 times by &1913, &1921
evntv_hi         = &0221
; &0221 referenced 2 times by &1919, &1926
autorun_index    = &023c  ; Running fill index into the keyboard buffer as the loader queues its PAGE / OLD / RUN commands.
; &023c referenced 4 times by &3969, &3974, &3977, &397e
kbd_buffer       = &0300  ; Base of the &0300 page holding the MOS keyboard buffer (&03E0-&03FF), written directly on the fast hand-off path.
; &0300 used as index base 1 time by &3971
basic_line10_len = &0c03  ; Length byte of the relocated BASIC's line 10, patched from 0 back to &16 so the protected program lists and runs.
; &0c03 referenced 1 time by &3963
os_signature     = &e8aa  ; OS ROM byte read (for 'O') to distinguish OS versions and choose the command hand-off path.
; &e8aa referenced 1 time by &3950
user_via_orb     = &fe60  ; User VIA port B: writes column strobes and the 74LS157 handset-select bit (bit 7); reads the four matrix rows.
; &fe60 referenced 8 times by &1939, &193c, &1945, &1948, &195c, &195f, &197f, &1982
user_via_ddrb    = &fe62  ; User VIA data-direction register B: set to &F0 so the four strobe/select lines are outputs, the four rows inputs.
; &fe62 referenced 1 time by &190f
osword           = &fff1  ; OSWORD: the resident driver calls OSWORD 7 to sound the key-click.
; &fff1 referenced 1 time by &19a8
osbyte           = &fff4  ; OSBYTE: A=&99 inserts a key into the buffer, A=&0E enables the vsync event, A=&8A inserts the loader's auto-run commands, and A=&C8 (200) sets the BREAK/ESCAPE effect.
; &fff4 referenced 4 times by &190a, &19bc, &398a, &399d
oscli            = &fff7  ; OSCLI: issues the single startup command "T." (*TAPE) to select the cassette filing system; the PAGE/OLD/RUN commands instead go through the keyboard buffer.
; &fff7 referenced 1 time by &39ae


    org &1900

; Move 1: &1900 to &0a00 for length 256
    org &0a00
; ***************************************************************************************
; Install the resident keypad driver
;
; Enable the 50 Hz vertical-sync event and route it to the matrix scanner. Sets User VIA
; port B to strobe the keypad (DDRB = &F0: top nibble out, bottom nibble in) and hooks
; EVNTV to point at the event handler, saving the previous vector at saved_evntv. Called
; from the BASIC front-end via CALL &A00.
;
; On Exit:
;     A: corrupted
;     X: corrupted
;     Y: corrupted
.install_driver
    php                                                               ; 1900: 08          . :0a00[1]          ; Preserve the caller flags
    pha                                                               ; 1901: 48          H :0a01[1]          ; Preserve A
    tya                                                               ; 1902: 98          . :0a02[1]          ; Preserve Y...
    pha                                                               ; 1903: 48          H :0a03[1]          ; ...on the stack
    txa                                                               ; 1904: 8a          . :0a04[1]          ; Preserve X...
    pha                                                               ; 1905: 48          H :0a05[1]          ; ...on the stack
    lda #&0e                                                          ; 1906: a9 0e       .. :0a06[1]         ; OSBYTE 14: enable an event...
    ldx #4                                                            ; 1908: a2 04       .. :0a08[1]         ; ...event 4, the 50 Hz vertical sync
    jsr osbyte                                                        ; 190a: 20 f4 ff     .. :0a0a[1]        ; call OSBYTE
    lda #&f0                                                          ; 190d: a9 f0       .. :0a0d[1]         ; DDRB = &F0: bits 4-7 drive the column strobes + 74LS157 select...
    sta user_via_ddrb                                                 ; 190f: 8d 62 fe    .b. :0a0f[1]        ; ...bits 0-3 sense the four row lines
    sei                                                               ; 1912: 78          x :0a12[1]          ; Block IRQs while re-pointing the vector
    lda evntv                                                         ; 1913: ad 20 02    . . :0a13[1]        ; Save the current event vector low byte...
    sta saved_evntv                                                   ; 1916: 8d fe 0a    ... :0a16[1]        ; ...at saved_evntv, to chain to on exit
    lda evntv_hi                                                      ; 1919: ad 21 02    .!. :0a19[1]        ; Save its high byte...
    sta saved_evntv_hi                                                ; 191c: 8d ff 0a    ... :0a1c[1]        ; ...too
    lda #&31 ; '1'                                                    ; 191f: a9 31       .1 :0a1f[1]         ; Point EVNTV at vsync_event_handler: low byte &31...
    sta evntv                                                         ; 1921: 8d 20 02    . . :0a21[1]        ; ...store it
    lda #&0a                                                          ; 1924: a9 0a       .. :0a24[1]         ; ...high byte &0A...
    sta evntv_hi                                                      ; 1926: 8d 21 02    .!. :0a26[1]        ; ...store it
    cli                                                               ; 1929: 58          X :0a29[1]          ; Re-enable IRQs
    pla                                                               ; 192a: 68          h :0a2a[1]          ; Restore X...
    tax                                                               ; 192b: aa          . :0a2b[1]          ; ...from the stack
    pla                                                               ; 192c: 68          h :0a2c[1]          ; Restore Y...
    tay                                                               ; 192d: a8          . :0a2d[1]          ; ...from the stack
    pla                                                               ; 192e: 68          h :0a2e[1]          ; Restore A
    plp                                                               ; 192f: 28          ( :0a2f[1]          ; Restore the flags
    rts                                                               ; 1930: 60          ` :0a30[1]          ; Return to the BASIC caller
; ***************************************************************************************
; Vertical-sync event handler: scan the keypad
;
; Entered from the MOS every 50 Hz vsync event. Strobes the 3x4 matrix through User VIA
; port B (bit 7 selects handset 0/1 via the 74LS157), debounces and auto-repeats via
; debounce_counter, and on a pressed key sounds a short key-click (OSWORD 7) and inserts
; the mapped character into the keyboard buffer (OSBYTE &99). Chains to the previous
; event vector on exit.
.vsync_event_handler
    php                                                               ; 1931: 08          . :0a31[1]          ; Preserve the interrupted flags
    pha                                                               ; 1932: 48          H :0a32[1]          ; Preserve A
    tya                                                               ; 1933: 98          . :0a33[1]          ; Preserve Y...
    pha                                                               ; 1934: 48          H :0a34[1]          ; ...on the stack
    txa                                                               ; 1935: 8a          . :0a35[1]          ; Preserve X...
    pha                                                               ; 1936: 48          H :0a36[1]          ; ...on the stack
    lda #0                                                            ; 1937: a9 00       .. :0a37[1]         ; Quick probe: drive every column low on handset 0...
    sta user_via_orb                                                  ; 1939: 8d 60 fe    .`. :0a39[1]        ; ...write it
    lda user_via_orb                                                  ; 193c: ad 60 fe    .`. :0a3c[1]        ; ...and read the rows back
    cmp #&0f                                                          ; 193f: c9 0f       .. :0a3f[1]         ; All four rows high (&0F) => nothing down on handset 0
    bne check_held_key                                                ; 1941: d0 0c       .. :0a41[1]         ; Something is down -> go locate it
    lda #&80                                                          ; 1943: a9 80       .. :0a43[1]         ; Probe handset 1 (bit 7 selects it)...
    sta user_via_orb                                                  ; 1945: 8d 60 fe    .`. :0a45[1]        ; ...write it
    lda user_via_orb                                                  ; 1948: ad 60 fe    .`. :0a48[1]        ; ...read the rows
    cmp #&8f                                                          ; 194b: c9 8f       .. :0a4b[1]         ; &8F = handset-1 select set, all rows high = no key
    beq no_key_down                                                   ; 194d: f0 73       .s :0a4d[1]         ; Nothing on either handset -> idle
; &0a4f referenced 1 time by &1941
.check_held_key
    ldy current_row                                                   ; 194f: ac d1 0a    ... :0a4f[1]        ; Is a key already being held? (current_row 5 = none)
    cpy #5                                                            ; 1952: c0 05       .. :0a52[1]         ; against the "none" marker (5)
    beq scan_matrix                                                   ; 1954: f0 1e       .. :0a54[1]         ; No held key -> full matrix scan
    ldx current_col                                                   ; 1956: ae d2 0a    ... :0a56[1]        ; Re-test the held key: fetch its column strobe...
    lda col_strobes,x                                                 ; 1959: bd d7 0a    ... :0a59[1]        ; from the strobe table
    sta user_via_orb                                                  ; 195c: 8d 60 fe    .`. :0a5c[1]        ; ...drive it
    lda user_via_orb                                                  ; 195f: ad 60 fe    .`. :0a5f[1]        ; ...read the rows...
    and row_masks,y                                                   ; 1962: 39 d3 0a    9.. :0a62[1]        ; ...and mask its row bit
    bne scan_matrix                                                   ; 1965: d0 0d       .. :0a65[1]         ; Released (bit high now) -> rescan for a new key
    dec debounce_counter                                              ; 1967: ce d0 0a    ... :0a67[1]        ; Still held: count down to the next auto-repeat (patched to LDA by the editor to disable auto-repeat)
    bne handler_exit                                                  ; 196a: d0 5b       .[ :0a6a[1]         ; Not time to repeat yet -> exit
    lda #4                                                            ; 196c: a9 04       .. :0a6c[1]         ; Reload the repeat interval (4 frames)...
    sta debounce_counter                                              ; 196e: 8d d0 0a    ... :0a6e[1]        ; store it
    clc                                                               ; 1971: 18          . :0a71[1]          ; clear carry for the branch
    bcc emit_key                                                      ; 1972: 90 2e       .. :0a72[1]         ; Re-emit the held key
; &0a74 referenced 2 times by &1954, &1965
.scan_matrix
    ldx #0                                                            ; 1974: a2 00       .. :0a74[1]         ; Full scan: start at column 0
; &0a76 referenced 1 time by &1992
.scan_next_column
    ldy #0                                                            ; 1976: a0 00       .. :0a76[1]         ; Start at row 0 of this column
; &0a78 referenced 1 time by &198d
.scan_next_row
    cpy #0                                                            ; 1978: c0 00       .. :0a78[1]         ; Only (re)strobe the column when starting at row 0...
    bne test_row                                                      ; 197a: d0 06       .. :0a7a[1]         ; ...otherwise the strobe already stands
    lda col_strobes,x                                                 ; 197c: bd d7 0a    ... :0a7c[1]        ; Drive column X (its handset bit included)...
    sta user_via_orb                                                  ; 197f: 8d 60 fe    .`. :0a7f[1]        ; write it
; &0a82 referenced 1 time by &197a
.test_row
    lda user_via_orb                                                  ; 1982: ad 60 fe    .`. :0a82[1]        ; Read the rows...
    and row_masks,y                                                   ; 1985: 39 d3 0a    9.. :0a85[1]        ; ...test this row bit
    beq key_pressed                                                   ; 1988: f0 0d       .. :0a88[1]         ; Bit low -> key at (column X, row Y) is pressed
    iny                                                               ; 198a: c8          . :0a8a[1]          ; Next row...
    cpy #4                                                            ; 198b: c0 04       .. :0a8b[1]         ; all four rows done?
    bne scan_next_row                                                 ; 198d: d0 e9       .. :0a8d[1]         ; ...until all 4 rows tested
    inx                                                               ; 198f: e8          . :0a8f[1]          ; Next column...
    cpx #6                                                            ; 1990: e0 06       .. :0a90[1]         ; ...6 columns = 3 per handset
    bne scan_next_column                                              ; 1992: d0 e2       .. :0a92[1]         ; loop back for the next column
    clc                                                               ; 1994: 18          . :0a94[1]          ; clear carry for the branch
    bcc handler_exit                                                  ; 1995: 90 30       .0 :0a95[1]         ; Nothing pressed -> exit
; &0a97 referenced 1 time by &1988
.key_pressed
    lda #&18                                                          ; 1997: a9 18       .. :0a97[1]         ; New press: set the initial auto-repeat delay (24 frames)...
    sta debounce_counter                                              ; 1999: 8d d0 0a    ... :0a99[1]        ; store it
    stx current_col                                                   ; 199c: 8e d2 0a    ... :0a9c[1]        ; Remember which key is now held: column...
    sty current_row                                                   ; 199f: 8c d1 0a    ... :0a9f[1]        ; ...and row
; &0aa2 referenced 1 time by &1972
.emit_key
    lda #7                                                            ; 19a2: a9 07       .. :0aa2[1]         ; OSWORD 7: play the key-click sound...
    ldx #&f6                                                          ; 19a4: a2 f6       .. :0aa4[1]         ; ...parameter block at sound_block (&0AF6)...
    ldy #&0a                                                          ; 19a6: a0 0a       .. :0aa6[1]         ; block high byte &0A
    jsr osword                                                        ; 19a8: 20 f1 ff     .. :0aa8[1]        ; call OSWORD
    clc                                                               ; 19ab: 18          . :0aab[1]          ; Key-table index = col*4 + row:
    lda current_col                                                   ; 19ac: ad d2 0a    ... :0aac[1]        ; take the column...
    asl a                                                             ; 19af: 0a          . :0aaf[1]          ; ...times 4...
    asl a                                                             ; 19b0: 0a          . :0ab0[1]          ; shifted twice = x4
    adc current_row                                                   ; 19b1: 6d d1 0a    m.. :0ab1[1]        ; ...plus the row
    tax                                                               ; 19b4: aa          . :0ab4[1]          ; ...as an index
    ldy key_codes,x                                                   ; 19b5: bc dd 0a    ... :0ab5[1]        ; Fetch that cell character into Y
    lda #&99                                                          ; 19b8: a9 99       .. :0ab8[1]         ; OSBYTE &99: insert Y into buffer 0 (keyboard)...
    ldx #0                                                            ; 19ba: a2 00       .. :0aba[1]         ; X=0 selects the keyboard buffer
    jsr osbyte                                                        ; 19bc: 20 f4 ff     .. :0abc[1]        ; ...as if the key were typed
    clc                                                               ; 19bf: 18          . :0abf[1]          ; clear carry for the branch
    bcc handler_exit                                                  ; 19c0: 90 05       .. :0ac0[1]         ; Done
; &0ac2 referenced 1 time by &194d
.no_key_down
    lda #5                                                            ; 19c2: a9 05       .. :0ac2[1]         ; Record 'no key held' (row 5)...
    sta current_row                                                   ; 19c4: 8d d1 0a    ... :0ac4[1]        ; store it
; &0ac7 referenced 3 times by &196a, &1995, &19c0
.handler_exit
    pla                                                               ; 19c7: 68          h :0ac7[1]          ; Restore X...
    tax                                                               ; 19c8: aa          . :0ac8[1]          ; into X
    pla                                                               ; 19c9: 68          h :0ac9[1]          ; Restore Y...
    tay                                                               ; 19ca: a8          . :0aca[1]          ; into Y
    pla                                                               ; 19cb: 68          h :0acb[1]          ; Restore A
    plp                                                               ; 19cc: 28          ( :0acc[1]          ; Restore the flags
    jmp (saved_evntv)                                                 ; 19cd: 6c fe 0a    l.. :0acd[1]        ; Chain to the event handler we displaced
; &0ad0 referenced 3 times by &1967, &196e, &1999
.debounce_counter
    equb &10                                                          ; 19d0: 10          . :0ad0[1]          ; Frames until the next auto-repeat (0 = repeat this frame)
; &0ad1 referenced 4 times by &194f, &199f, &19b1, &19c4
.current_row
    equb &04                                                          ; 19d1: 04          . :0ad1[1]          ; Row of the held key (5 = none)
; &0ad2 referenced 3 times by &1956, &199c, &19ac
.current_col
    equb &00                                                          ; 19d2: 00          . :0ad2[1]          ; Column of the held key
; &0ad3 used as index base 2 times by &1962, &1985
.row_masks
    equb &08, &04, &02, &01                                           ; 19d3: 08 04 02... ...... :0ad3[1]     ; Port-B input bit for matrix rows 0-3
; &0ad7 used as index base 2 times by &1959, &197c
.col_strobes
    equb &60, &50, &30, &e0, &d0, &b0                                 ; 19d7: 60 50 30... `P0... :0ad7[1]     ; Port-B strobe per column: cols 0-2 = handset 0 (&60,&50,&30), cols 3-5 = handset 1 (bit 7 set for the 74LS157)
; &0add used as index base 1 time by &19b5
.key_codes
    equb &7f                                                          ; 19dd: 7f          . :0add[1]          ; Default character per cell, indexed col*4+row: cells 0-11 handset 0 (digits/DELETE/RETURN), cells 12-23 handset 1 (letters). The editor overwrites this table.
    equs "1470258"                                                    ; 19de: 31 34 37... 147... :0ade[1]   
    equb &0d                                                          ; 19e5: 0d          . :0ae5[1]        
    equs "369ADGJBEHKCFIL"                                            ; 19e6: 33 36 39... 369... :0ae6[1]   
    equb &00                                                          ; 19f5: 00          . :0af5[1]          ; Spare byte
.sound_block
    equw &0000, &fff8, &80, &0001                                     ; 19f6: 00 00 f8... ...... :0af6[1]     ; OSWORD 7 block: channel &0000, amplitude &FFF8 (patched by the editor beep option), pitch &0080, duration &0001
; &0afe referenced 2 times by &1916, &19cd
.saved_evntv
; &19ff referenced 1 time by &191c
saved_evntv_hi = saved_evntv+1
    equw &0000                                                        ; 19fe: 00 00       .. :0afe[1]         ; Previous EVNTV, chained to on exit


    ; Copy the newly assembled block of code back to it's proper place in the binary
    ; file.
    ; (Note the parameter order: 'copyblock <start>,<end>,<dest>')
    copyblock install_driver, *, &1900

    ; Clear the area of memory we just temporarily used to assemble the new block,
    ; allowing us to assemble there again if needed
    clear install_driver, &0b00

    ; Set the program counter to the next position in the binary file.
    org &1900 + (* - install_driver)


    org &1900

.dasmos_start

    org &1a00
; Image of page &0B (the MOS soft-key/function-key buffer). The relocator skips page &0B so the user keys survive, making these bytes inert filler.
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a00: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a0c: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a18: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a24: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a30: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a3c: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a48: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a54: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a60: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a6c: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a78: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a84: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a90: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1a9c: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1aa8: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1ab4: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1ac0: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1acc: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1ad8: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1ae4: 10 10 10... ......
    equb &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10, &10   ; 1af0: 10 10 10... ......
    equb &10, &10, &10, &10                                           ; 1afc: 10 10 10... ......
; ROL-encoded tokenised BASIC (the keypad-definition editor); relocates to PAGE=&0C00 and is decrypted in place. Source: basic/voltmace-delta-14b-driver-keypad.bas.
    incbin "voltmace-delta-14b-driver-keypad-basic.dat"               ; 1b00: 86 00 05... ......
; Zero padding between the encrypted BASIC and the *RUN loader
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 3869: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 3875: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 3881: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 388d: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 3899: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38a5: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38b1: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38bd: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38c9: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38d5: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38e1: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00, &00   ; 38ed: 00 00 00... ......
    equb &00, &00, &00, &00, &00, &00, &00                            ; 38f9: 00 00 00... ......
; Filler ahead of the loader entry; reads as a stub BASIC line (&0D, line 13, then RTS bytes)
.loader_preamble
    equb &0d, &00, &0d, &60, &60, &60                                 ; 3900: 0d 00 0d... ......
; ***************************************************************************************
; *RUN entry: relocate, decode, and auto-run
;
; The file system execution address (*RUN entry-point) for this binary. Relocates the
; whole image down to &0A00 (installing the resident driver code and moving the encrypted
; BASIC to PAGE &0C00), decrypts the BASIC in place, then queues 'PAGE=&C00 / OLD / RUN'
; so the now-plain BASIC front-end starts.
.main
    pha                                                               ; 3906: 48          H        ; Preserve A
    txa                                                               ; 3907: 8a          .        ; Preserve X...
    pha                                                               ; 3908: 48          H        ; ...on the stack
    tya                                                               ; 3909: 98          .        ; Preserve Y...
    pha                                                               ; 390a: 48          H        ; ...on the stack
    jsr relocate_image                                                ; 390b: 20 aa 39     .9      ; Copy the image down (resident driver to &0A00, BASIC to PAGE &0C00)
    jsr decode_basic                                                  ; 390e: 20 1d 39     .9      ; Decrypt the relocated BASIC in place
    jsr patch_basic_header                                            ; 3911: 20 61 39     a9      ; Repair the BASIC's first-line length byte
    jsr os_dependent_setup                                            ; 3914: 20 4e 39     N9      ; Queue the auto-run commands (OS-dependent)
    pla                                                               ; 3917: 68          h        ; Restore Y...
    tay                                                               ; 3918: a8          .        ; into Y
    pla                                                               ; 3919: 68          h        ; Restore X...
    tax                                                               ; 391a: aa          .        ; into X
    pla                                                               ; 391b: 68          h        ; Restore A
    rts                                                               ; 391c: 60          `        ; Return to the MOS; the queued commands then run the BASIC
; ***************************************************************************************
; Decrypt the relocated BASIC
;
; Rotate every byte of the relocated BASIC left one bit (the inverse of the ROL-1 storage
; protection), across pages &0C00-&2AFF, in place.
; &391d referenced 1 time by &390e
.decode_basic
    lda decode_ptr                                                    ; 391d: a5 80       ..       ; Save the caller decode_ptr low byte...
    sta decode_ptr_save                                               ; 391f: 8d 5f 39    ._9      ; save it
    lda decode_ptr_hi                                                 ; 3922: a5 81       ..       ; ...and high byte...
    sta decode_ptr_save_hi                                            ; 3924: 8d 60 39    .`9      ; ...at decode_ptr_save
    ldx #0                                                            ; 3927: a2 00       ..       ; Point decode_ptr at PAGE &0C00: low byte 0...
    stx decode_ptr                                                    ; 3929: 86 80       ..       ; set it
    ldx #&0c                                                          ; 392b: a2 0c       ..       ; ...high byte &0C...
    ldy #0                                                            ; 392d: a0 00       ..       ; byte index 0
; &392f referenced 1 time by &3941
.decode_next_page
    stx decode_ptr_hi                                                 ; 392f: 86 81       ..       ; Set the page being decrypted
; &3931 referenced 1 time by &393a
.decode_next_byte
    lda (decode_ptr),y                                                ; 3931: b1 80       ..       ; Read an encrypted byte...
    clc                                                               ; 3933: 18          .        ; redundant CLC: the ASL below sets carry from bit 7 itself
    asl a                                                             ; 3934: 0a          .        ; ...rotate it left one bit (undo the ROL-1 protection)...
    adc #0                                                            ; 3935: 69 00       i.       ; ...carrying bit 7 into bit 0...
    sta (decode_ptr),y                                                ; 3937: 91 80       ..       ; ...and store it back
    iny                                                               ; 3939: c8          .        ; Next byte...
    bne decode_next_byte                                              ; 393a: d0 f5       ..       ; ...to the end of the page
    ldx decode_ptr_hi                                                 ; 393c: a6 81       ..       ; Next page...
    inx                                                               ; 393e: e8          .        ; increment the page
    cpx #&2b ; '+'                                                    ; 393f: e0 2b       .+       ; ...until page &2B (end of the BASIC region)
    bne decode_next_page                                              ; 3941: d0 ec       ..       ; keep decrypting pages
    lda decode_ptr_save                                               ; 3943: ad 5f 39    ._9      ; Restore the caller decode_ptr...
    sta decode_ptr                                                    ; 3946: 85 80       ..       ; low byte
    lda decode_ptr_save_hi                                            ; 3948: ad 60 39    .`9      ; high byte
    sta decode_ptr_hi                                                 ; 394b: 85 81       ..       ; store it
    rts                                                               ; 394d: 60          `        ; Done
; ***************************************************************************************
; OS-version-dependent setup
;
; Reads os_signature to pick how the auto-run commands are queued.
; &394e referenced 1 time by &3914
.os_dependent_setup
    ldy #0                                                            ; 394e: a0 00       ..       ; clear Y
    lda os_signature                                                  ; 3950: ad aa e8    ...      ; Read the OS ROM signature byte...
    cmp #&4f ; 'O'                                                    ; 3953: c9 4f       .O       ; ...'O' (&4F) is the OS 0.1 signature (the OS the BASIC rejects)
    beq use_direct_poke                                               ; 3955: f0 04       ..       ; OS 0.1 -> poke the buffer directly
    jsr setup_keys                                                    ; 3957: 20 86 39     .9      ; other (supported) OS -> insert via OSBYTE &8A
    rts                                                               ; 395a: 60          `        ; Done
; &395b referenced 1 time by &3955
.use_direct_poke
    jsr queue_autorun                                                 ; 395b: 20 67 39     g9      ; Queue by poking the keyboard buffer
    rts                                                               ; 395e: 60          `        ; Done
; &395f referenced 2 times by &391f, &3943
.decode_ptr_save
; &3960 referenced 2 times by &3924, &3948
decode_ptr_save_hi = decode_ptr_save+1
    equw &eaea                                                        ; 395f: ea ea       ..       ; Scratch: caller's decode_ptr saved across decode_basic (&EAEA at rest)
; ***************************************************************************************
; Repair the BASIC program's first line
;
; Write &16 (22) into basic_line10_len, the length byte of the line-10 REM at PAGE=&0C00.
; That byte is stored as 0 (part of the protection), so without this repair the relocated
; program cannot be LISTed or RUN.
; &3961 referenced 1 time by &3911
.patch_basic_header
    lda #&16                                                          ; 3961: a9 16       ..       ; The first BASIC line is 22 bytes long...
    sta basic_line10_len                                              ; 3963: 8d 03 0c    ...      ; ...restore its length byte (stored as 0 by the protection)
    rts                                                               ; 3966: 60          `        ; Done
; ***************************************************************************************
; Queue the auto-run commands (direct poke)
;
; Copy autorun_commands into the MOS keyboard buffer so the OS reads them as typed and
; runs the decoded BASIC. autorun_index wraps into the 32-byte buffer at &03E0-&03FF.
; &3967 referenced 1 time by &395b
.queue_autorun
    ldy #0                                                            ; 3967: a0 00       ..       ; Start at the first command byte
; &3969 referenced 1 time by &3982
.queue_next_byte
    ldx autorun_index                                                 ; 3969: ae 3c 02    .<.      ; Current buffer fill position...
    lda autorun_commands,y                                            ; 396c: b9 f4 39    ..9      ; read a command byte...
    beq queue_done                                                    ; 396f: f0 14       ..       ; ...&00 terminates
    sta kbd_buffer,x                                                  ; 3971: 9d 00 03    ...      ; Poke it into the keyboard buffer
    inc autorun_index                                                 ; 3974: ee 3c 02    .<.      ; Advance the fill position...
    lda autorun_index                                                 ; 3977: ad 3c 02    .<.      ; reload it
    bne queue_advance                                                 ; 397a: d0 05       ..       ; unless it wrapped to 0
    lda #&e0                                                          ; 397c: a9 e0       ..       ; ...wrapping back to &E0 (buffer at &03E0)...
    sta autorun_index                                                 ; 397e: 8d 3c 02    .<.      ; store it
; &3981 referenced 1 time by &397a
.queue_advance
    iny                                                               ; 3981: c8          .        ; Next command byte
    jmp queue_next_byte                                               ; 3982: 4c 69 39    Li9      ; loop
; &3985 referenced 1 time by &396f
.queue_done
    rts                                                               ; 3985: 60          `        ; Done
; ***************************************************************************************
; Queue the auto-run commands (OSBYTE path)
;
; The non-&4F-OS variant of queue_autorun: set the BREAK/ESCAPE behaviour, then insert
; each autorun_commands byte with OSBYTE &8A.
; &3986 referenced 1 time by &3957
.setup_keys
    lda #&c8                                                          ; 3986: a9 c8       ..       ; OSBYTE 200: set the BREAK/ESCAPE behaviour...
    ldx #3                                                            ; 3988: a2 03       ..       ; value 3
    jsr osbyte                                                        ; 398a: 20 f4 ff     ..      ; call OSBYTE
    ldx #0                                                            ; 398d: a2 00       ..       ; Start at the first command byte
; &398f referenced 1 time by &39a5
.insert_next_key
    lda autorun_commands,x                                            ; 398f: bd f4 39    ..9      ; Read a command byte...
    beq setup_keys_done                                               ; 3992: f0 14       ..       ; ...&00 terminates
    tay                                                               ; 3994: a8          .        ; The character to insert
    txa                                                               ; 3995: 8a          .        ; Save the loop index...
    sta setup_key_index                                               ; 3996: 8d a9 39    ..9      ; save it
    ldx #0                                                            ; 3999: a2 00       ..       ; OSBYTE &8A: insert Y into buffer 0 (keyboard)...
    lda #&8a                                                          ; 399b: a9 8a       ..       ; A = &8A
    jsr osbyte                                                        ; 399d: 20 f4 ff     ..      ; call OSBYTE
    lda setup_key_index                                               ; 39a0: ad a9 39    ..9      ; Restore the loop index...
    tax                                                               ; 39a3: aa          .        ; into X
    inx                                                               ; 39a4: e8          .        ; Next command byte
    jmp insert_next_key                                               ; 39a5: 4c 8f 39    L.9      ; loop
; &39a8 referenced 1 time by &3992
.setup_keys_done
    rts                                                               ; 39a8: 60          `        ; Done
; &39a9 referenced 2 times by &3996, &39a0
.setup_key_index
    equb &ea                                                          ; 39a9: ea          .        ; Scratch: saved loop index (&EA at rest)
; ***************************************************************************************
; Relocate the program image to &0A00
;
; OSCLI the startup command, then block-copy the image from &1900 down to &0A00
; (copy_pages pages via copy_src -> copy_dst), skipping destination page &0B so the
; soft-key buffer survives.
; &39aa referenced 1 time by &390b
.relocate_image
    ldx #&f1                                                          ; 39aa: a2 f1       ..       ; OSCLI the startup command at oscli_command (&39F1): low byte...
    ldy #&39 ; '9'                                                    ; 39ac: a0 39       .9       ; ...high byte...
    jsr oscli                                                         ; 39ae: 20 f7 ff     ..      ; ...call OSCLI
    sec                                                               ; 39b1: 38          8        ; (carry set; not used by the copy below)
    lda #0                                                            ; 39b2: a9 00       ..       ; Leftover byte count = 0 (whole pages only)...
    sta copy_rem                                                      ; 39b4: 85 74       .t       ; store it
    lda #&20 ; ' '                                                    ; 39b6: a9 20       .        ; Copy &20 = 32 pages...
    sta copy_pages                                                    ; 39b8: 85 75       .u       ; store it
    lda #0                                                            ; 39ba: a9 00       ..       ; Destination = &0A00: low byte...
    sta copy_dst                                                      ; 39bc: 85 70       .p       ; store it
    lda #&0a                                                          ; 39be: a9 0a       ..       ; ...high byte...
    sta copy_dst_hi                                                   ; 39c0: 85 71       .q       ; store it
    lda #0                                                            ; 39c2: a9 00       ..       ; Source = &1900 (the loaded image): low byte...
    sta copy_src                                                      ; 39c4: 85 72       .r       ; store it
    lda #&19                                                          ; 39c6: a9 19       ..       ; ...high byte...
    sta copy_src_hi                                                   ; 39c8: 85 73       .s       ; store it
    ldy #0                                                            ; 39ca: a0 00       ..       ; Byte index within the page
    ldx copy_pages                                                    ; 39cc: a6 75       .u       ; Page count...
    beq copy_remainder                                                ; 39ce: f0 14       ..       ; ...none -> just the remainder
; &39d0 referenced 2 times by &39db, &39e2
.copy_page
    lda copy_dst_hi                                                   ; 39d0: a5 71       .q       ; Which destination page are we about to write?
    cmp #&0b                                                          ; 39d2: c9 0b       ..       ; Leave page &0B untouched so the user soft-key definitions survive the move
    beq copy_next_byte                                                ; 39d4: f0 04       ..       ; ...skip the store for that page
    lda (copy_src),y                                                  ; 39d6: b1 72       .r       ; Copy one byte...
    sta (copy_dst),y                                                  ; 39d8: 91 70       .p       ; to the destination
; &39da referenced 1 time by &39d4
.copy_next_byte
    iny                                                               ; 39da: c8          .        ; Next byte...
    bne copy_page                                                     ; 39db: d0 f3       ..       ; ...to the end of the page
    inc copy_src_hi                                                   ; 39dd: e6 73       .s       ; Next source page...
    inc copy_dst_hi                                                   ; 39df: e6 71       .q       ; ...and destination page
    dex                                                               ; 39e1: ca          .        ; one fewer page
    bne copy_page                                                     ; 39e2: d0 ec       ..       ; ...until all pages copied
; &39e4 referenced 1 time by &39ce
.copy_remainder
    ldx copy_rem                                                      ; 39e4: a6 74       .t       ; Any leftover bytes? (none here)
    beq copy_done                                                     ; 39e6: f0 08       ..       ; none -> done
; &39e8 referenced 1 time by &39ee
.copy_remainder_byte
    lda (copy_src),y                                                  ; 39e8: b1 72       .r       ; Copy one byte...
    sta (copy_dst),y                                                  ; 39ea: 91 70       .p       ; to the destination
    iny                                                               ; 39ec: c8          .        ; next byte
    dex                                                               ; 39ed: ca          .        ; one fewer
    bne copy_remainder_byte                                           ; 39ee: d0 f8       ..       ; loop
; &39f0 referenced 1 time by &39e6
.copy_done
    rts                                                               ; 39f0: 60          `        ; Done
.oscli_command
    equs "T."                                                         ; 39f1: 54 2e       T.       ; Startup *-command "T." (*TAPE): select the cassette filing system, CR-terminated
    equb &0d                                                          ; 39f3: 0d          .     
; &39f4 used as index base 2 times by &396c, &398f
.autorun_commands
    equb &15, &0d                                                     ; 39f4: 15 0d       ..       ; CTRL-U + CR: clear the input line
    equs "PA.=&C00"                                                   ; 39f6: 50 41 2e... PA....   ; set PAGE to &0C00, where the BASIC now lives
    equb &0d                                                          ; 39fe: 0d          .        ; submit
    equs "OLD"                                                        ; 39ff: 4f 4c 44    OLD      ; reinstate the decoded program (OLD)
    equb &0d                                                          ; 3a02: 0d          .        ; submit
    equs "RUN"                                                        ; 3a03: 52 55 4e    RUN      ; run it (RUN)
    equb &0d, &00                                                     ; 3a06: 0d 00       ..       ; submit; the &00 then stops the queue copy
; Uninitialised tail of the saved image. The file is a memory dump &1900-&3A80 (the BASIC clears exactly TO &3A80); the loader's code and tables end ~120 bytes short, so this holds whatever occupied the memory at save time. It is referenced by nothing and decodes as neither 6502, tokenised BASIC (raw or bit-rotated), nor text; its byte statistics are those of noise. Inert: the BASIC memory-clear overwrites it at startup.
.trailing_data
    equb &0d, &83, &fc, &a6, &9a, &0e, &ef, &7c, &d1, &53, &48, &0a   ; 3a08: 0d 83 fc... ......
    equb &df, &19, &6b, &a3, &c5, &a4, &06, &e7, &f8, &19, &48, &da   ; 3a14: df 19 6b... ..k...
    equb &ac, &0d, &d7, &7f, &bb, &95, &91, &6b, &05, &c7, &e8, &5f   ; 3a20: ac 0d d7... ......
    equb &61, &3b, &08, &08, &84, &ca, &16, &93, &a6, &d3, &cf, &15   ; 3a2c: 61 3b 08... a;....
    equb &1a, &51, &34, &6f, &e4, &40, &f0, &19, &ba, &96, &05, &df   ; 3a38: 1a 51 34... .Q4...
    equb &fd, &73, &81, &03, &cf, &d8, &09, &fc, &48, &31, &0a, &67   ; 3a44: fd 73 81... .s....
    equb &eb, &bc, &3a, &0d, &29, &34, &d7, &11, &e9, &6b, &d0, &32   ; 3a50: eb bc 3a... ..:...
    equb &a0, &34, &38, &0d, &5e, &8b, &9f, &63, &35, &41, &4b, &8c   ; 3a5c: a0 34 38... .48...
    equb &2b, &fc, &01, &19, &16, &2d, &e0, &39, &c7, &e0, &8b, &36   ; 3a68: 2b fc 01... +.....
    equb &53, &a2, &ac, &b4, &25, &a8, &21, &5d, &1c, &5d, &35, &2f   ; 3a74: 53 a2 ac... S.....
.dasmos_end

save dasmos_start, dasmos_end, &3906, &1900

; Label references by decreasing frequency:
;     user_via_orb:         8
;     decode_ptr:           5
;     autorun_index:        4
;     current_row:          4
;     decode_ptr_hi:        4
;     osbyte:               4
;     copy_dst:             3
;     copy_dst_hi:          3
;     copy_src:             3
;     current_col:          3
;     debounce_counter:     3
;     handler_exit:         3
;     autorun_commands:     2
;     col_strobes:          2
;     copy_page:            2
;     copy_pages:           2
;     copy_rem:             2
;     copy_src_hi:          2
;     decode_ptr_save:      2
;     decode_ptr_save_hi:   2
;     evntv:                2
;     evntv_hi:             2
;     row_masks:            2
;     saved_evntv:          2
;     scan_matrix:          2
;     setup_key_index:      2
;     basic_line10_len:     1
;     check_held_key:       1
;     copy_done:            1
;     copy_next_byte:       1
;     copy_remainder:       1
;     copy_remainder_byte:  1
;     decode_basic:         1
;     decode_next_byte:     1
;     decode_next_page:     1
;     emit_key:             1
;     insert_next_key:      1
;     kbd_buffer:           1
;     key_codes:            1
;     key_pressed:          1
;     no_key_down:          1
;     os_dependent_setup:   1
;     os_signature:         1
;     oscli:                1
;     osword:               1
;     patch_basic_header:   1
;     queue_advance:        1
;     queue_autorun:        1
;     queue_done:           1
;     queue_next_byte:      1
;     relocate_image:       1
;     saved_evntv_hi:       1
;     scan_next_column:     1
;     scan_next_row:        1
;     setup_keys:           1
;     setup_keys_done:      1
;     test_row:             1
;     use_direct_poke:      1
;     user_via_ddrb:        1

; Stats:
;     Total size (Code + Data) = 8576 bytes
;     Code                     = 440 bytes (5%)
;     Data                     = 8136 bytes (95%)
;
;     Number of instructions   = 224
;     Number of data bytes     = 557 bytes
;     Number of data words     = 12 bytes
;     Number of string bytes   = 38 bytes
;     Number of strings        = 6
;     Number of included bytes = 7529 bytes
;     Number of includes       = 1
