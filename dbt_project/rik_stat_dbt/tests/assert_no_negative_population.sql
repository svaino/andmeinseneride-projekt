select *
from {{ ref('int_stat_rahvastik') }}
where elanike_arv < 0