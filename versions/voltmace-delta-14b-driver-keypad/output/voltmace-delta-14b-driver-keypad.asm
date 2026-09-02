; Memory locations
copy_dst         = &70
; &70 referenced 3 times by &39bc, &39d8, &39ea
copy_dst_hi      = &71
; &71 referenced 3 times by &39c0, &39d0, &39df
copy_src         = &72
; &72 referenced 3 times by &39c4, &39d6, &39e8
copy_src_hi      = &73
; &73 referenced 2 times by &39c8, &39dd
copy_rem         = &74
; &74 referenced 2 times by &39b4, &39e4
copy_pages       = &75
; &75 referenced 2 times by &39b8, &39cc
decode_ptr       = &80
; &80 referenced 5 times by &391d, &3929, &3931, &3937, &3946
decode_ptr_hi    = &81
; &81 referenced 4 times by &3922, &392f, &393c, &394b
evntv            = &0220
; &0220 referenced 2 times by &1913, &1921
evntv_hi         = &0221
; &0221 referenced 2 times by &1919, &1926
autorun_index    = &023c
; &023c referenced 4 times by &3969, &3974, &3977, &397e
l0300            = &0300
; &0300 used as index base 1 time by &3971
basic_line10_len = &0c03
; &0c03 referenced 1 time by &3963
os_signature     = &e8aa
; &e8aa referenced 1 time by &3950
user_via_orb     = &fe60
; &fe60 referenced 8 times by &1939, &193c, &1945, &1948, &195c, &195f, &197f, &1982
user_via_ddrb    = &fe62
; &fe62 referenced 1 time by &190f
osword           = &fff1
; &fff1 referenced 1 time by &19a8
osbyte           = &fff4
; &fff4 referenced 4 times by &190a, &19bc, &398a, &399d
oscli            = &fff7
; &fff7 referenced 1 time by &39ae


    org &1900

; Move 1: &1900 to &0a00 for length 256
    org &0a00
; ***************************************************************************************
; Install the keypad driver
;
; Enable the 50 Hz vertical-sync event and route it to the matrix scanner. Sets User VIA
; port B to strobe the keypad (DDRB = &F0: top nibble out, bottom nibble in) and hooks
; EVNTV to point at the event handler, saving the previous vector at saved_evntv. Called
; from the BASIC front-end via CALL &A00.
.install_driver
    php                                                               ; 1900: 08          . :0a00[1]        
    pha                                                               ; 1901: 48          H :0a01[1]        
    tya                                                               ; 1902: 98          . :0a02[1]        
    pha                                                               ; 1903: 48          H :0a03[1]        
    txa                                                               ; 1904: 8a          . :0a04[1]        
    pha                                                               ; 1905: 48          H :0a05[1]        
; Ask the MOS to fire an event on every 50 Hz vertical sync (OSBYTE 14, event 4)
    lda #&0e                                                          ; 1906: a9 0e       .. :0a06[1]       
    ldx #4                                                            ; 1908: a2 04       .. :0a08[1]       
    jsr osbyte                                                        ; 190a: 20 f4 ff     .. :0a0a[1]      
; Drive the column strobes and 74LS157 handset-select as outputs and sense the four row lines as inputs
    lda #&f0                                                          ; 190d: a9 f0       .. :0a0d[1]       
    sta user_via_ddrb                                                 ; 190f: 8d 62 fe    .b. :0a0f[1]      
    sei                                                               ; 1912: 78          x :0a12[1]        
; Remember whoever currently owns the event vector, to chain to
    lda evntv                                                         ; 1913: ad 20 02    . . :0a13[1]      
    sta saved_evntv                                                   ; 1916: 8d fe 0a    ... :0a16[1]      
    lda evntv_hi                                                      ; 1919: ad 21 02    .!. :0a19[1]      
    sta l0aff                                                         ; 191c: 8d ff 0a    ... :0a1c[1]      
; Take over EVNTV so each vsync enters the scanner
    lda #&31 ; '1'                                                    ; 191f: a9 31       .1 :0a1f[1]       
    sta evntv                                                         ; 1921: 8d 20 02    . . :0a21[1]      
    lda #&0a                                                          ; 1924: a9 0a       .. :0a24[1]       
    sta evntv_hi                                                      ; 1926: 8d 21 02    .!. :0a26[1]      
    cli                                                               ; 1929: 58          X :0a29[1]        
    pla                                                               ; 192a: 68          h :0a2a[1]        
    tax                                                               ; 192b: aa          . :0a2b[1]        
    pla                                                               ; 192c: 68          h :0a2c[1]        
    tay                                                               ; 192d: a8          . :0a2d[1]        
    pla                                                               ; 192e: 68          h :0a2e[1]        
    plp                                                               ; 192f: 28          ( :0a2f[1]        
    rts                                                               ; 1930: 60          ` :0a30[1]        
; ***************************************************************************************
; Vertical-sync event handler: scan the keypad
;
; Entered from the MOS every 50 Hz vsync event. Strobes the 3x4 matrix through User VIA
; port B (bit 7 selects handset 0/1 via the 74LS157), debounces via debounce_counter, and
; on a newly-pressed key sounds a short beep (OSWORD 7) and inserts the mapped character
; into the keyboard buffer (OSBYTE &99). Chains to the previous event vector on exit.
.vsync_event_handler
    php                                                               ; 1931: 08          . :0a31[1]        
    pha                                                               ; 1932: 48          H :0a32[1]        
    tya                                                               ; 1933: 98          . :0a33[1]        
    pha                                                               ; 1934: 48          H :0a34[1]        
    txa                                                               ; 1935: 8a          . :0a35[1]        
    pha                                                               ; 1936: 48          H :0a36[1]        
; Probe for activity: strobe all columns low and read the rows back
    lda #0                                                            ; 1937: a9 00       .. :0a37[1]       
    sta user_via_orb                                                  ; 1939: 8d 60 fe    .`. :0a39[1]      
    lda user_via_orb                                                  ; 193c: ad 60 fe    .`. :0a3c[1]      
    cmp #&0f                                                          ; 193f: c9 0f       .. :0a3f[1]       
    bne c0a4f                                                         ; 1941: d0 0c       .. :0a41[1]       
    lda #&80                                                          ; 1943: a9 80       .. :0a43[1]       
    sta user_via_orb                                                  ; 1945: 8d 60 fe    .`. :0a45[1]      
    lda user_via_orb                                                  ; 1948: ad 60 fe    .`. :0a48[1]      
    cmp #&8f                                                          ; 194b: c9 8f       .. :0a4b[1]       
    beq c0ac2                                                         ; 194d: f0 73       .s :0a4d[1]       
; &0a4f referenced 1 time by &1941
.c0a4f
    ldy current_row                                                   ; 194f: ac d1 0a    ... :0a4f[1]      
    cpy #5                                                            ; 1952: c0 05       .. :0a52[1]       
    beq c0a74                                                         ; 1954: f0 1e       .. :0a54[1]       
    ldx current_col                                                   ; 1956: ae d2 0a    ... :0a56[1]      
    lda col_strobes,x                                                 ; 1959: bd d7 0a    ... :0a59[1]      
    sta user_via_orb                                                  ; 195c: 8d 60 fe    .`. :0a5c[1]      
    lda user_via_orb                                                  ; 195f: ad 60 fe    .`. :0a5f[1]      
    and row_masks,y                                                   ; 1962: 39 d3 0a    9.. :0a62[1]      
    bne c0a74                                                         ; 1965: d0 0d       .. :0a65[1]       
    dec debounce_counter                                              ; 1967: ce d0 0a    ... :0a67[1]      
    bne c0ac7                                                         ; 196a: d0 5b       .[ :0a6a[1]       
    lda #4                                                            ; 196c: a9 04       .. :0a6c[1]       
    sta debounce_counter                                              ; 196e: 8d d0 0a    ... :0a6e[1]      
    clc                                                               ; 1971: 18          . :0a71[1]        
    bcc c0aa2                                                         ; 1972: 90 2e       .. :0a72[1]       
; &0a74 referenced 2 times by &1954, &1965
.c0a74
    ldx #0                                                            ; 1974: a2 00       .. :0a74[1]       
; &0a76 referenced 1 time by &1992
.c0a76
    ldy #0                                                            ; 1976: a0 00       .. :0a76[1]       
; &0a78 referenced 1 time by &198d
.c0a78
    cpy #0                                                            ; 1978: c0 00       .. :0a78[1]       
    bne c0a82                                                         ; 197a: d0 06       .. :0a7a[1]       
    lda col_strobes,x                                                 ; 197c: bd d7 0a    ... :0a7c[1]      
    sta user_via_orb                                                  ; 197f: 8d 60 fe    .`. :0a7f[1]      
; &0a82 referenced 1 time by &197a
.c0a82
    lda user_via_orb                                                  ; 1982: ad 60 fe    .`. :0a82[1]      
    and row_masks,y                                                   ; 1985: 39 d3 0a    9.. :0a85[1]      
    beq c0a97                                                         ; 1988: f0 0d       .. :0a88[1]       
    iny                                                               ; 198a: c8          . :0a8a[1]        
    cpy #4                                                            ; 198b: c0 04       .. :0a8b[1]       
    bne c0a78                                                         ; 198d: d0 e9       .. :0a8d[1]       
    inx                                                               ; 198f: e8          . :0a8f[1]        
    cpx #6                                                            ; 1990: e0 06       .. :0a90[1]       
    bne c0a76                                                         ; 1992: d0 e2       .. :0a92[1]       
    clc                                                               ; 1994: 18          . :0a94[1]        
    bcc c0ac7                                                         ; 1995: 90 30       .0 :0a95[1]       
; &0a97 referenced 1 time by &1988
.c0a97
    lda #&18                                                          ; 1997: a9 18       .. :0a97[1]       
    sta debounce_counter                                              ; 1999: 8d d0 0a    ... :0a99[1]      
    stx current_col                                                   ; 199c: 8e d2 0a    ... :0a9c[1]      
    sty current_row                                                   ; 199f: 8c d1 0a    ... :0a9f[1]      
; Acknowledge the press with a short key-click (OSWORD 7)
; &0aa2 referenced 1 time by &1972
.c0aa2
    lda #7                                                            ; 19a2: a9 07       .. :0aa2[1]       
    ldx #&f6                                                          ; 19a4: a2 f6       .. :0aa4[1]       
    ldy #&0a                                                          ; 19a6: a0 0a       .. :0aa6[1]       
    jsr osword                                                        ; 19a8: 20 f1 ff     .. :0aa8[1]      
    clc                                                               ; 19ab: 18          . :0aab[1]        
    lda current_col                                                   ; 19ac: ad d2 0a    ... :0aac[1]      
    asl a                                                             ; 19af: 0a          . :0aaf[1]        
    asl a                                                             ; 19b0: 0a          . :0ab0[1]        
; Look up the character for this matrix cell (col*4 + row)
    adc current_row                                                   ; 19b1: 6d d1 0a    m.. :0ab1[1]      
    tax                                                               ; 19b4: aa          . :0ab4[1]        
    ldy key_codes,x                                                   ; 19b5: bc dd 0a    ... :0ab5[1]      
; Deliver the keystroke into the keyboard buffer as if typed (OSBYTE &99)
    lda #&99                                                          ; 19b8: a9 99       .. :0ab8[1]       
    ldx #0                                                            ; 19ba: a2 00       .. :0aba[1]       
    jsr osbyte                                                        ; 19bc: 20 f4 ff     .. :0abc[1]      
    clc                                                               ; 19bf: 18          . :0abf[1]        
    bcc c0ac7                                                         ; 19c0: 90 05       .. :0ac0[1]       
; &0ac2 referenced 1 time by &194d
.c0ac2
    lda #5                                                            ; 19c2: a9 05       .. :0ac2[1]       
    sta current_row                                                   ; 19c4: 8d d1 0a    ... :0ac4[1]      
; &0ac7 referenced 3 times by &196a, &1995, &19c0
.c0ac7
    pla                                                               ; 19c7: 68          h :0ac7[1]        
    tax                                                               ; 19c8: aa          . :0ac8[1]        
    pla                                                               ; 19c9: 68          h :0ac9[1]        
    tay                                                               ; 19ca: a8          . :0aca[1]        
    pla                                                               ; 19cb: 68          h :0acb[1]        
    plp                                                               ; 19cc: 28          ( :0acc[1]        
; Hand the event on to the handler we displaced
    jmp (saved_evntv)                                                 ; 19cd: 6c fe 0a    l.. :0acd[1]      
; &0ad0 referenced 3 times by &1967, &196e, &1999
.debounce_counter
    equb &10                                                          ; 19d0: 10          . :0ad0[1]        
; &0ad1 referenced 4 times by &194f, &199f, &19b1, &19c4
.current_row
    equb &04                                                          ; 19d1: 04          . :0ad1[1]        
; &0ad2 referenced 3 times by &1956, &199c, &19ac
.current_col
    equb &00                                                          ; 19d2: 00          . :0ad2[1]        
; input-bit mask for each of the 4 matrix rows
; &0ad3 used as index base 2 times by &1962, &1985
.row_masks
    equb &08, &04, &02, &01                                           ; 19d3: 08 04 02... ...... :0ad3[1]   
; column strobes: the 3 columns for handset 0 (&60,&50,&30) then handset 1 (bit 7 set selects it via the 74LS157)
; &0ad7 used as index base 2 times by &1959, &197c
.col_strobes
    equs "`P0"                                                        ; 19d7: 60 50 30    `P0 :0ad7[1]      
    equb &e0, &d0, &b0                                                ; 19da: e0 d0 b0    ... :0ada[1]      
; default character for each of the 24 cells (col*4+row): handset 0 = digits/DELETE/RETURN, handset 1 = letters A-L
; &0add used as index base 1 time by &19b5
.key_codes
    equb &7f                                                          ; 19dd: 7f          . :0add[1]        
    equs "1470258"                                                    ; 19de: 31 34 37... 147... :0ade[1]   
    equb &0d                                                          ; 19e5: 0d          . :0ae5[1]        
    equs "369ADGJBEHKCFIL"                                            ; 19e6: 33 36 39... 369... :0ae6[1]   
    equb &00                                                          ; 19f5: 00          . :0af5[1]        
; OSWORD 7 parameter block: channel, amplitude, pitch, duration
.sound_block
    equb &00, &00, &f8, &ff, &80, &00, &01, &00                       ; 19f6: 00 00 f8... ...... :0af6[1]   
; previous EVNTV, restored by the JMP (saved_evntv)
; &0afe referenced 2 times by &1916, &19cd
.saved_evntv
; &19ff referenced 1 time by &191c
l0aff = saved_evntv+1
    equb &00, &00                                                     ; 19fe: 00 00       .. :0afe[1]       


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

.pydis_start

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
; The DFS execution address. Relocates the whole image down to &0A00 (installing the
; driver code and moving the encrypted BASIC to PAGE &0C00), decrypts the BASIC in place,
; then queues 'PAGE=&C00 / OLD / RUN' so the now-plain BASIC front-end starts.
.main
    pha                                                               ; 3906: 48          H     
    txa                                                               ; 3907: 8a          .     
    pha                                                               ; 3908: 48          H     
    tya                                                               ; 3909: 98          .     
    pha                                                               ; 390a: 48          H     
    jsr relocate_image                                                ; 390b: 20 aa 39     .9   
    jsr decode_basic                                                  ; 390e: 20 1d 39     .9   
    jsr patch_basic_header                                            ; 3911: 20 61 39     a9   
    jsr os_dependent_setup                                            ; 3914: 20 4e 39     N9   
    pla                                                               ; 3917: 68          h     
    tay                                                               ; 3918: a8          .     
    pla                                                               ; 3919: 68          h     
    tax                                                               ; 391a: aa          .     
    pla                                                               ; 391b: 68          h     
    rts                                                               ; 391c: 60          `     
; ***************************************************************************************
; Decrypt the relocated BASIC
;
; Rotate every byte of the relocated BASIC left one bit (the inverse of the ROL-1 storage
; protection), across pages &0C00-&2AFF, in place.
; &391d referenced 1 time by &390e
.decode_basic
    lda decode_ptr                                                    ; 391d: a5 80       ..    
    sta l395f                                                         ; 391f: 8d 5f 39    ._9   
    lda decode_ptr_hi                                                 ; 3922: a5 81       ..    
    sta l3960                                                         ; 3924: 8d 60 39    .`9   
    ldx #0                                                            ; 3927: a2 00       ..    
    stx decode_ptr                                                    ; 3929: 86 80       ..    
    ldx #&0c                                                          ; 392b: a2 0c       ..    
    ldy #0                                                            ; 392d: a0 00       ..    
; &392f referenced 1 time by &3941
.loop_c392f
    stx decode_ptr_hi                                                 ; 392f: 86 81       ..    
; &3931 referenced 1 time by &393a
.loop_c3931
    lda (decode_ptr),y                                                ; 3931: b1 80       ..    
    clc                                                               ; 3933: 18          .     
    asl a                                                             ; 3934: 0a          .     
    adc #0                                                            ; 3935: 69 00       i.    
    sta (decode_ptr),y                                                ; 3937: 91 80       ..    
    iny                                                               ; 3939: c8          .     
    bne loop_c3931                                                    ; 393a: d0 f5       ..    
    ldx decode_ptr_hi                                                 ; 393c: a6 81       ..    
    inx                                                               ; 393e: e8          .     
    cpx #&2b ; '+'                                                    ; 393f: e0 2b       .+    
    bne loop_c392f                                                    ; 3941: d0 ec       ..    
    lda l395f                                                         ; 3943: ad 5f 39    ._9   
    sta decode_ptr                                                    ; 3946: 85 80       ..    
    lda l3960                                                         ; 3948: ad 60 39    .`9   
    sta decode_ptr_hi                                                 ; 394b: 85 81       ..    
    rts                                                               ; 394d: 60          `     
; ***************************************************************************************
; OS-version-dependent setup
;
; Reads os_signature to choose between the two setup paths below.
; &394e referenced 1 time by &3914
.os_dependent_setup
    ldy #0                                                            ; 394e: a0 00       ..    
    lda os_signature                                                  ; 3950: ad aa e8    ...   
    cmp #&4f ; 'O'                                                    ; 3953: c9 4f       .O    
    beq c395b                                                         ; 3955: f0 04       ..    
    jsr setup_keys                                                    ; 3957: 20 86 39     .9   
    rts                                                               ; 395a: 60          `     
; &395b referenced 1 time by &3955
.c395b
    jsr queue_autorun                                                 ; 395b: 20 67 39     g9   
    rts                                                               ; 395e: 60          `     
; &395f referenced 2 times by &391f, &3943
.l395f
; &3960 referenced 2 times by &3924, &3948
l3960 = l395f+1
    equb &ea, &ea                                                     ; 395f: ea ea       ..    
; ***************************************************************************************
; Repair the BASIC program's first line
;
; Write &16 (22) into basic_line10_len, the length byte of the line-10 REM at PAGE=&0C00.
; That byte is stored as 0 (part of the protection), so without this repair the relocated
; program cannot be LISTed or RUN.
; &3961 referenced 1 time by &3911
.patch_basic_header
    lda #&16                                                          ; 3961: a9 16       ..    
    sta basic_line10_len                                              ; 3963: 8d 03 0c    ...   
    rts                                                               ; 3966: 60          `     
; ***************************************************************************************
; Queue the auto-run command string
;
; Copy autorun_commands ('PA.=&C00' / 'OLD' / 'RUN') into the input buffer so the MOS
; 'types' them and the decoded BASIC runs.
; &3967 referenced 1 time by &395b
.queue_autorun
    ldy #0                                                            ; 3967: a0 00       ..    
; &3969 referenced 1 time by &3982
.c3969
    ldx autorun_index                                                 ; 3969: ae 3c 02    .<.   
    lda autorun_commands,y                                            ; 396c: b9 f4 39    ..9   
    beq return_1                                                      ; 396f: f0 14       ..    
    sta l0300,x                                                       ; 3971: 9d 00 03    ...   
    inc autorun_index                                                 ; 3974: ee 3c 02    .<.   
    lda autorun_index                                                 ; 3977: ad 3c 02    .<.   
    bne c3981                                                         ; 397a: d0 05       ..    
    lda #&e0                                                          ; 397c: a9 e0       ..    
    sta autorun_index                                                 ; 397e: 8d 3c 02    .<.   
; &3981 referenced 1 time by &397a
.c3981
    iny                                                               ; 3981: c8          .     
    jmp c3969                                                         ; 3982: 4c 69 39    Li9   
; &3985 referenced 1 time by &396f
.return_1
    rts                                                               ; 3985: 60          `     
; ***************************************************************************************
; Alternate key setup (OSBYTE path)
; &3986 referenced 1 time by &3957
.setup_keys
    lda #&c8                                                          ; 3986: a9 c8       ..    
    ldx #3                                                            ; 3988: a2 03       ..    
    jsr osbyte                                                        ; 398a: 20 f4 ff     ..   
    ldx #0                                                            ; 398d: a2 00       ..    
; &398f referenced 1 time by &39a5
.c398f
    lda autorun_commands,x                                            ; 398f: bd f4 39    ..9   
    beq return_2                                                      ; 3992: f0 14       ..    
    tay                                                               ; 3994: a8          .     
    txa                                                               ; 3995: 8a          .     
    sta l39a9                                                         ; 3996: 8d a9 39    ..9   
    ldx #0                                                            ; 3999: a2 00       ..    
    lda #&8a                                                          ; 399b: a9 8a       ..    
    jsr osbyte                                                        ; 399d: 20 f4 ff     ..   
    lda l39a9                                                         ; 39a0: ad a9 39    ..9   
    tax                                                               ; 39a3: aa          .     
    inx                                                               ; 39a4: e8          .     
    jmp c398f                                                         ; 39a5: 4c 8f 39    L.9   
; &39a8 referenced 1 time by &3992
.return_2
    rts                                                               ; 39a8: 60          `     
; &39a9 referenced 2 times by &3996, &39a0
.l39a9
    equb &ea                                                          ; 39a9: ea          .     
; ***************************************************************************************
; Relocate the program image to &0A00
;
; OSCLI the command at oscli_command, then block-copy the image from &1900 down to &0A00
; (copy_pages pages via copy_src -> copy_dst), skipping destination page &0B so the
; soft-key buffer survives.
; &39aa referenced 1 time by &390b
.relocate_image
    ldx #&f1                                                          ; 39aa: a2 f1       ..    
    ldy #&39 ; '9'                                                    ; 39ac: a0 39       .9    
    jsr oscli                                                         ; 39ae: 20 f7 ff     ..   
    sec                                                               ; 39b1: 38          8     
    lda #0                                                            ; 39b2: a9 00       ..    
    sta copy_rem                                                      ; 39b4: 85 74       .t    
    lda #&20 ; ' '                                                    ; 39b6: a9 20       .     
    sta copy_pages                                                    ; 39b8: 85 75       .u    
    lda #0                                                            ; 39ba: a9 00       ..    
    sta copy_dst                                                      ; 39bc: 85 70       .p    
    lda #&0a                                                          ; 39be: a9 0a       ..    
    sta copy_dst_hi                                                   ; 39c0: 85 71       .q    
    lda #0                                                            ; 39c2: a9 00       ..    
    sta copy_src                                                      ; 39c4: 85 72       .r    
    lda #&19                                                          ; 39c6: a9 19       ..    
    sta copy_src_hi                                                   ; 39c8: 85 73       .s    
    ldy #0                                                            ; 39ca: a0 00       ..    
    ldx copy_pages                                                    ; 39cc: a6 75       .u    
    beq c39e4                                                         ; 39ce: f0 14       ..    
; &39d0 referenced 2 times by &39db, &39e2
.c39d0
    lda copy_dst_hi                                                   ; 39d0: a5 71       .q    
    cmp #&0b                                                          ; 39d2: c9 0b       ..       ; Leave page &0B untouched so the user soft-key definitions survive the move
    beq c39da                                                         ; 39d4: f0 04       ..    
    lda (copy_src),y                                                  ; 39d6: b1 72       .r    
    sta (copy_dst),y                                                  ; 39d8: 91 70       .p    
; &39da referenced 1 time by &39d4
.c39da
    iny                                                               ; 39da: c8          .     
    bne c39d0                                                         ; 39db: d0 f3       ..    
    inc copy_src_hi                                                   ; 39dd: e6 73       .s    
    inc copy_dst_hi                                                   ; 39df: e6 71       .q    
    dex                                                               ; 39e1: ca          .     
    bne c39d0                                                         ; 39e2: d0 ec       ..    
; &39e4 referenced 1 time by &39ce
.c39e4
    ldx copy_rem                                                      ; 39e4: a6 74       .t    
    beq return_3                                                      ; 39e6: f0 08       ..    
; &39e8 referenced 1 time by &39ee
.loop_c39e8
    lda (copy_src),y                                                  ; 39e8: b1 72       .r    
    sta (copy_dst),y                                                  ; 39ea: 91 70       .p    
    iny                                                               ; 39ec: c8          .     
    dex                                                               ; 39ed: ca          .     
    bne loop_c39e8                                                    ; 39ee: d0 f8       ..    
; &39f0 referenced 1 time by &39e6
.return_3
    rts                                                               ; 39f0: 60          `     
.oscli_command
    equs "T.", &0d                                                    ; 39f1: 54 2e 0d    T..      ; startup command "*T." (*TAPE): select the cassette filing system before relocating
; &39f4 used as index base 2 times by &396c, &398f
.autorun_commands
    equb &15, &0d                                                     ; 39f4: 15 0d       ..       ; auto-run command lines: 'PA.=&C00' / 'OLD' / 'RUN', CR-separated, &00-terminated
    equs "PA.=&C00"                                                   ; 39f6: 50 41 2e... PA....
    equb &0d                                                          ; 39fe: 0d          .     
    equs "OLD"                                                        ; 39ff: 4f 4c 44    OLD   
    equb &0d                                                          ; 3a02: 0d          .     
    equs "RUN"                                                        ; 3a03: 52 55 4e    RUN   
; Trailing bytes the loader never references; the relocated copy is wiped by the BASIC memory-clear (FOR A%=&C00 TO &3A80) at startup
.trailing_data
    equb &0d, &00, &0d, &83, &fc, &a6, &9a, &0e, &ef, &7c, &d1, &53   ; 3a06: 0d 00 0d... ......
    equb &48, &0a, &df, &19, &6b, &a3, &c5, &a4, &06, &e7, &f8, &19   ; 3a12: 48 0a df... H.....
    equb &48, &da, &ac, &0d, &d7, &7f, &bb, &95, &91, &6b, &05, &c7   ; 3a1e: 48 da ac... H.....
    equb &e8, &5f, &61, &3b, &08, &08, &84, &ca, &16, &93, &a6, &d3   ; 3a2a: e8 5f 61... ._a...
    equb &cf, &15, &1a, &51, &34, &6f, &e4, &40, &f0, &19, &ba, &96   ; 3a36: cf 15 1a... ......
    equb &05, &df, &fd, &73, &81, &03, &cf, &d8, &09, &fc, &48, &31   ; 3a42: 05 df fd... ......
    equb &0a, &67, &eb, &bc, &3a, &0d, &29, &34, &d7, &11, &e9, &6b   ; 3a4e: 0a 67 eb... .g....
    equb &d0, &32, &a0, &34, &38, &0d, &5e, &8b, &9f, &63, &35, &41   ; 3a5a: d0 32 a0... .2....
    equb &4b, &8c, &2b, &fc, &01, &19, &16, &2d, &e0, &39, &c7, &e0   ; 3a66: 4b 8c 2b... K.+...
    equb &8b, &36, &53, &a2, &ac, &b4, &25, &a8, &21, &5d, &1c, &5d   ; 3a72: 8b 36 53... .6S...
    equb &35, &2f                                                     ; 3a7e: 35 2f       5/    
.pydis_end

save pydis_start, pydis_end, &3906, &1900

; Label references by decreasing frequency:
;     user_via_orb:        8
;     decode_ptr:          5
;     autorun_index:       4
;     current_row:         4
;     decode_ptr_hi:       4
;     osbyte:              4
;     c0ac7:               3
;     copy_dst:            3
;     copy_dst_hi:         3
;     copy_src:            3
;     current_col:         3
;     debounce_counter:    3
;     autorun_commands:    2
;     c0a74:               2
;     c39d0:               2
;     col_strobes:         2
;     copy_pages:          2
;     copy_rem:            2
;     copy_src_hi:         2
;     evntv:               2
;     evntv_hi:            2
;     l395f:               2
;     l3960:               2
;     l39a9:               2
;     row_masks:           2
;     saved_evntv:         2
;     basic_line10_len:    1
;     c0a4f:               1
;     c0a76:               1
;     c0a78:               1
;     c0a82:               1
;     c0a97:               1
;     c0aa2:               1
;     c0ac2:               1
;     c395b:               1
;     c3969:               1
;     c3981:               1
;     c398f:               1
;     c39da:               1
;     c39e4:               1
;     decode_basic:        1
;     key_codes:           1
;     l0300:               1
;     l0aff:               1
;     loop_c392f:          1
;     loop_c3931:          1
;     loop_c39e8:          1
;     os_dependent_setup:  1
;     os_signature:        1
;     oscli:               1
;     osword:              1
;     patch_basic_header:  1
;     queue_autorun:       1
;     relocate_image:      1
;     return_1:            1
;     return_2:            1
;     return_3:            1
;     setup_keys:          1
;     user_via_ddrb:       1

; Automatically generated labels:
;     c0a4f
;     c0a74
;     c0a76
;     c0a78
;     c0a82
;     c0a97
;     c0aa2
;     c0ac2
;     c0ac7
;     c395b
;     c3969
;     c3981
;     c398f
;     c39d0
;     c39da
;     c39e4
;     l0300
;     l0aff
;     l395f
;     l3960
;     l39a9
;     loop_c392f
;     loop_c3931
;     loop_c39e8
;     return_1
;     return_2
;     return_3

; Stats:
;     Total size (Code + Data) = 8576 bytes
;     Code                     = 440 bytes (5%)
;     Data                     = 8136 bytes (95%)
;
;     Number of instructions   = 224
;     Number of data bytes     = 565 bytes
;     Number of data words     = 0 bytes
;     Number of string bytes   = 42 bytes
;     Number of strings        = 7
;     Number of included bytes = 7529 bytes
;     Number of includes       = 1
