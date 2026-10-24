! Read one complete legacy namelist without treating malformed input as clean EOF.
! Physical equations remain in the original fixed-form source files.
subroutine read_namelist_cards(unit, group, cards, status)
  implicit none
  integer, intent(in) :: unit
  character(*), intent(in) :: group
  character(*), intent(out) :: cards
  integer, intent(out) :: status
  character(1024) :: line, lower
  character :: quote, c
  integer :: ios, n, i, k, used, finish
  logical :: started
  cards = ''
  used = 0
  started = .false.
  quote = ' '
  status = 1
  do
    read(unit, '(A)', iostat=ios) line
    if (ios < 0) then
      if (.not. started) status = -1
      return
    endif
    if (ios /= 0) return
    n = len_trim(line)
    if (n == len(line)) return ! Explicit record limit; never silently truncate.
    if (.not. started) then
      lower = adjustl(line)
      if (len_trim(lower) == 0) cycle
      if (lower(1:1) == '!') cycle
      do i = 1, len_trim(lower)
        k = iachar(lower(i:i))
        if (k >= iachar('A') .and. k <= iachar('Z')) lower(i:i) = achar(k+32)
      enddo
      if (lower(1:1) /= '&' .and. lower(1:1) /= '$') return
      k = len_trim(group)
      if (lower(2:k+1) /= group) return
      c = lower(k+2:k+2)
      if (c /= ' ' .and. c /= ',' .and. c /= '/' .and. c /= achar(9)) return
      started = .true.
    endif
    finish = 0
    i = 1
    do while (i <= n)
      c = line(i:i)
      if (quote /= ' ') then
        if (c == quote) then
          if (i < n) then
            if (line(i+1:i+1) == quote) then
              i = i+2
              cycle
            endif
          endif
          quote = ' '
        endif
      else
        if (c == '!') exit
        if (c == "'" .or. c == '"') quote = c
        if (c == '/') finish = i
        if ((c == '&' .or. c == '$') .and. i+3 <= n) then
          lower = line
          do k = i+1, i+3
            if (iachar(lower(k:k)) >= 65 .and. iachar(lower(k:k)) <= 90) &
              lower(k:k) = achar(iachar(lower(k:k))+32)
          enddo
          if (lower(i+1:i+3) == 'end') finish = i+3
        endif
        if (finish > 0) exit
      endif
      i = i+1
    enddo
    if (finish > 0) then
      lower = adjustl(line(finish+1:))
      if (len_trim(lower) > 0) then
        if (lower(1:1) /= '!') return
      endif
      n = finish
    endif
    if (used+n+1 > len(cards)) return
    cards(used+1:used+n+1) = line(:n)//achar(10)
    used = used+n+1
    if (finish > 0) then
      status = 0
      return
    endif
  enddo
end subroutine
