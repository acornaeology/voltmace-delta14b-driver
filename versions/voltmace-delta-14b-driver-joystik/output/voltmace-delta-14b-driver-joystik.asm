; Memory locations
l0080 = &80
; &80 referenced 5 times by &191d, &1929, &1931, &1937, &1946
l0081 = &81
; &81 referenced 4 times by &1922, &192f, &193c, &194b
l023c = &023c
; &023c referenced 4 times by &197e, &1989, &198c, &1993
l0300 = &0300
; &0300 used as index base 1 time by &1986
le8aa = &e8aa
; &e8aa referenced 1 time by &1950
le8ab = &e8ab
; &e8ab referenced 1 time by &1958
le8ac = &e8ac
; &e8ac referenced 1 time by &1960
lfff4 = &fff4
; &fff4 referenced 2 times by &199f, &19b2


    org &1900

.dasmos_start
.decoy
    equb &0d, &00, &0d, &60, &60, &60, &60, &60, &60                  ; 1900: 0d 00 0d... ......
    pha                                                               ; 1909: 48          H     
    txa                                                               ; 190a: 8a          .     
    pha                                                               ; 190b: 48          H     
    tya                                                               ; 190c: 98          .     
    pha                                                               ; 190d: 48          H     
    jsr sub_c191d                                                     ; 190e: 20 1d 19     ..   
    jsr sub_c1976                                                     ; 1911: 20 76 19     v.   
    jsr sub_c194e                                                     ; 1914: 20 4e 19     N.   
    pla                                                               ; 1917: 68          h     
    tay                                                               ; 1918: a8          .     
    pla                                                               ; 1919: 68          h     
    tax                                                               ; 191a: aa          .     
    pla                                                               ; 191b: 68          h     
    rts                                                               ; 191c: 60          `     
; &191d referenced 1 time by &190e
.sub_c191d
    lda l0080                                                         ; 191d: a5 80       ..    
    sta l1974                                                         ; 191f: 8d 74 19    .t.   
    lda l0081                                                         ; 1922: a5 81       ..    
    sta l1975                                                         ; 1924: 8d 75 19    .u.   
    ldx #0                                                            ; 1927: a2 00       ..    
    stx l0080                                                         ; 1929: 86 80       ..    
    ldx #&1a                                                          ; 192b: a2 1a       ..    
    ldy #0                                                            ; 192d: a0 00       ..    
; &192f referenced 1 time by &1941
.loop_c192f
    stx l0081                                                         ; 192f: 86 81       ..    
; &1931 referenced 1 time by &193a
.loop_c1931
    lda (l0080),y                                                     ; 1931: b1 80       ..    
    clc                                                               ; 1933: 18          .     
    asl a                                                             ; 1934: 0a          .     
    adc #0                                                            ; 1935: 69 00       i.    
    sta (l0080),y                                                     ; 1937: 91 80       ..    
    iny                                                               ; 1939: c8          .     
    bne loop_c1931                                                    ; 193a: d0 f5       ..    
    ldx l0081                                                         ; 193c: a6 81       ..    
    inx                                                               ; 193e: e8          .     
    cpx #&4b ; 'K'                                                    ; 193f: e0 4b       .K    
    bne loop_c192f                                                    ; 1941: d0 ec       ..    
    lda l1974                                                         ; 1943: ad 74 19    .t.   
    sta l0080                                                         ; 1946: 85 80       ..    
    lda l1975                                                         ; 1948: ad 75 19    .u.   
    sta l0081                                                         ; 194b: 85 81       ..    
    rts                                                               ; 194d: 60          `     
; &194e referenced 1 time by &1914
.sub_c194e
    ldy #0                                                            ; 194e: a0 00       ..    
    lda le8aa                                                         ; 1950: ad aa e8    ...   
    cmp #&4f ; 'O'                                                    ; 1953: c9 4f       .O    
    bne c1958                                                         ; 1955: d0 01       ..    
    iny                                                               ; 1957: c8          .     
; &1958 referenced 1 time by &1955
.c1958
    lda le8ab                                                         ; 1958: ad ab e8    ...   
    cmp #&53 ; 'S'                                                    ; 195b: c9 53       .S    
    bne c1960                                                         ; 195d: d0 01       ..    
    iny                                                               ; 195f: c8          .     
; &1960 referenced 1 time by &195d
.c1960
    lda le8ac                                                         ; 1960: ad ac e8    ...   
    cmp #&20 ; ' '                                                    ; 1963: c9 20       .     
    bne c1968                                                         ; 1965: d0 01       ..    
    iny                                                               ; 1967: c8          .     
; &1968 referenced 1 time by &1965
.c1968
    cpy #3                                                            ; 1968: c0 03       ..    
    beq c1970                                                         ; 196a: f0 04       ..    
    jsr sub_c199b                                                     ; 196c: 20 9b 19     ..   
    rts                                                               ; 196f: 60          `     
; &1970 referenced 1 time by &196a
.c1970
    jsr sub_c197c                                                     ; 1970: 20 7c 19     |.   
    rts                                                               ; 1973: 60          `     
; &1974 referenced 2 times by &191f, &1943
.l1974
; &1975 referenced 2 times by &1924, &1948
l1975 = l1974+1
    equb &00, &00                                                     ; 1974: 00 00       ..    
; &1976 referenced 1 time by &1911
.sub_c1976
    lda #&17                                                          ; 1976: a9 17       ..    
    sta l1c03                                                         ; 1978: 8d 03 1c    ...   
    rts                                                               ; 197b: 60          `     
; &197c referenced 1 time by &1970
.sub_c197c
    ldy #0                                                            ; 197c: a0 00       ..    
; &197e referenced 1 time by &1997
.c197e
    ldx l023c                                                         ; 197e: ae 3c 02    .<.   
    lda l19bf,y                                                       ; 1981: b9 bf 19    ...   
    beq return_1                                                      ; 1984: f0 14       ..    
    sta l0300,x                                                       ; 1986: 9d 00 03    ...   
    inc l023c                                                         ; 1989: ee 3c 02    .<.   
    lda l023c                                                         ; 198c: ad 3c 02    .<.   
    bne c1996                                                         ; 198f: d0 05       ..    
    lda #&e0                                                          ; 1991: a9 e0       ..    
    sta l023c                                                         ; 1993: 8d 3c 02    .<.   
; &1996 referenced 1 time by &198f
.c1996
    iny                                                               ; 1996: c8          .     
    jmp c197e                                                         ; 1997: 4c 7e 19    L~.   
; &199a referenced 1 time by &1984
.return_1
    rts                                                               ; 199a: 60          `     
; &199b referenced 1 time by &196c
.sub_c199b
    lda #&c8                                                          ; 199b: a9 c8       ..    
    ldx #3                                                            ; 199d: a2 03       ..    
    jsr lfff4                                                         ; 199f: 20 f4 ff     ..   
    ldx #0                                                            ; 19a2: a2 00       ..    
; &19a4 referenced 1 time by &19ba
.c19a4
    lda l19bf,x                                                       ; 19a4: bd bf 19    ...   
    beq return_2                                                      ; 19a7: f0 14       ..    
    tay                                                               ; 19a9: a8          .     
    txa                                                               ; 19aa: 8a          .     
    sta l19be                                                         ; 19ab: 8d be 19    ...   
    ldx #0                                                            ; 19ae: a2 00       ..    
    lda #&8a                                                          ; 19b0: a9 8a       ..    
    jsr lfff4                                                         ; 19b2: 20 f4 ff     ..   
    lda l19be                                                         ; 19b5: ad be 19    ...   
    tax                                                               ; 19b8: aa          .     
    inx                                                               ; 19b9: e8          .     
    jmp c19a4                                                         ; 19ba: 4c a4 19    L..   
; &19bd referenced 1 time by &19a7
.return_2
    rts                                                               ; 19bd: 60          `     
; &19be referenced 2 times by &19ab, &19b5
.l19be
; &19bf used as index base 2 times by &1981, &19a4
l19bf = l19be+1
    equb &ea, &15, &0d                                                ; 19be: ea 15 0d    ...   
    equs "PA.=&1C00"                                                  ; 19c1: 50 41 2e... PA....
    equb &0d                                                          ; 19ca: 0d          .     
    equs "OLD"                                                        ; 19cb: 4f 4c 44    OLD   
    equb &0d                                                          ; 19ce: 0d          .     
    equs "RUN"                                                        ; 19cf: 52 55 4e    RUN   
    equb &0d, &00, &0d                                                ; 19d2: 0d 00 0d    ...   
    equs "TgB"                                                        ; 19d5: 54 67 42    TgB   
    equb &cc, &6d, &f6, &b0, &c0, &ff                                 ; 19d8: cc 6d f6... .m....
    equs "8%M"                                                        ; 19de: 38 25 4d    8%M   
    equb &05, &55, &06, &b7, &84, &20, &d6, &88, &b0, &40, &bd, &d3   ; 19e1: 05 55 06... .U....
    equb &fa, &c8, &10, &f8, &f1, &eb, &44, &1b, &4c, &01, &63, &f6   ; 19ed: fa c8 10... ......
    equs "Pt!9q"                                                      ; 19f9: 50 74 21... Pt!...
    equb &c0, &86                                                     ; 19fe: c0 86       ..    
.sub_c1a00
; &1c03 referenced 1 time by &1978
l1c03 = sub_c1a00+515
    incbin "voltmace-delta-14b-driver-joystik-encoded.dat"            ; 1a00: 24 d4 86... $.....
.tail
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
;     l0080:       5
;     l0081:       4
;     l023c:       4
;     l1974:       2
;     l1975:       2
;     l19be:       2
;     l19bf:       2
;     lfff4:       2
;     c1958:       1
;     c1960:       1
;     c1968:       1
;     c1970:       1
;     c197e:       1
;     c1996:       1
;     c19a4:       1
;     l0300:       1
;     l1c03:       1
;     le8aa:       1
;     le8ab:       1
;     le8ac:       1
;     loop_c192f:  1
;     loop_c1931:  1
;     return_1:    1
;     return_2:    1
;     sub_c191d:   1
;     sub_c194e:   1
;     sub_c1976:   1
;     sub_c197c:   1
;     sub_c199b:   1

; Automatically generated labels:
;     c1958
;     c1960
;     c1968
;     c1970
;     c197e
;     c1996
;     c19a4
;     l0080
;     l0081
;     l023c
;     l0300
;     l1974
;     l1975
;     l19be
;     l19bf
;     l1c03
;     le8aa
;     le8ab
;     le8ac
;     lfff4
;     loop_c192f
;     loop_c1931
;     return_1
;     return_2
;     sub_c191d
;     sub_c194e
;     sub_c1976
;     sub_c197c
;     sub_c199b
;     sub_c1a00

; Stats:
;     Total size (Code + Data) = 13312 bytes
;     Code                     = 179 bytes (1%)
;     Data                     = 13133 bytes (99%)
;
;     Number of instructions   = 91
;     Number of data bytes     = 160 bytes
;     Number of data words     = 0 bytes
;     Number of string bytes   = 26 bytes
;     Number of strings        = 6
;     Number of included bytes = 12947 bytes
;     Number of includes       = 1
