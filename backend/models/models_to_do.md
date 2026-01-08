# moulds
```sh
class Mould(models.Model):
    POBYT_FORMY = {
        (0, 'PRODUKCJA'),
        (1, 'NARZEDZIOWNIA'),
        (2, 'KOOPERACJA'),
        (3, 'MAGAZYN_FORM')
    }
    STAN_FORMY = {
        (0, 'PRODUKCYJNA'),
        (1, 'TPM'),
        (2, 'AWARIA'),
        (3, 'MODYFIKACJA'),
        (4, 'PRZEZBRAJANA'),
        (5, 'W PRZEGLĄDZIE')
    }
    mould_number = UpperCaseCharField(max_length=128)
    product = models.TextField(default="")
    released = models.DateField(null=True, blank=True, default='1990-01-01')
    mould_photo = models.ImageField(upload_to='photos/%Y/%m/%d/')
    product_photo = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    hot_system_photo = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    extra_photo_1 = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    extra_photo_2 = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    extra_photo_3 = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    extra_photo_4 = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    extra_photo_5 = models.ImageField(upload_to='photos/%Y/%m/%d/', null=True, blank=True)
    num_of_cavities = models.CharField(null=True, blank=True, max_length=128)
    tool_weight = models.CharField(null=True, blank=True, max_length=128)
    total_cycles = models.IntegerField(default=0)
    to_maint_cycles = models.IntegerField(default=0)
    from_maint_cycles = models.IntegerField(default=0)
    place = models.IntegerField(default=0, choices=POBYT_FORMY)
    status = models.IntegerField(default=0, choices=STAN_FORMY)

    def __str__(self):
       return self.name_with_description()
       # return self.name_with_year()

    def name_with_year(self):
        return str(self.mould_number) + " (" + str(self.year) + ")"

    def name_with_description(self):
        return str(self.mould_number) + " (" + str(self.product) + ")"

    def to_maint(self):
        # print('to maint:', self.to_maint_cycles)
        # print('from maint:', self.from_maint_cycles)
        return int(int(self.from_maint_cycles) / int(self.to_maint_cycles) * 100)

    def jaki_stan_formy(self):
        # STAN_FORMY3 = {(0, 'PRODUKCYJNA'), (1, 'TPM'), (2, 'AWARIA'), (3, 'MODYFIKACJA')}
        STAN_FORMY2 = list(sorted(self.STAN_FORMY))
        # a = str(STAN_FORMY2[0]) 
        return STAN_FORMY2[self.status][1]
    
    def gdzie_forma(self):
        POBYT_FORMY2 = list(sorted(self.POBYT_FORMY))
        return POBYT_FORMY2[self.place][1]

        # return 100
    def sort(self):
        if self.to_maint() > 0:
            return 1 / self.to_maint()
        else:
            return 0.1 

```

# moulds tpms
```sh
class MouldsTpm(models.Model):
    CZAS_REAKCJI = {
        (0, 'NATYCHMIAST'),
        (1, 'W TRKACIE PRZEGLADU'),
        (2, 'PO ZAKONCZONEJ PRODUKCJI'),
    }
 
    STATUSY = {
        (0, 'OTWARTY'),
        (1, 'W TRAKCIE REALIZACJI'),
        (2, 'ZAMKNIĘTY'),
        (3, 'ODRZUCONY')
    }
    mould_id = models.ForeignKey(Mould, on_delete=models.CASCADE, related_name='tpm')
    sv = models.IntegerField(null=True, default=0, blank=True)
    created = models.DateField(auto_now_add=True)
    extra_photo_1 = models.ImageField(upload_to='photos/book/%Y/%m/%d/', null=True, blank=True)
    extra_photo_2 = models.ImageField(upload_to='photos/book/%Y/%m/%d/', null=True, blank=True)
    tpm_time_type = models.IntegerField(default=0, choices=CZAS_REAKCJI)
    opis_zgloszenia = models.TextField(null=True, verbose_name='opis_zgloszenia')
    ido = models.IntegerField(default=0, null=True, blank=True)
    status = models.IntegerField(default=0, choices=STATUSY)
    changed = models.DateField(null=True)
    author = models.TextField(null=True, blank=True, verbose_name='author')
    
    def __str__(self):
           return self.name_with_description()
       # return self.name_with_year()
    
    def name_with_description(self):
        return str(self.created) + " / " + str(self.mould_id) + " / "  + str(self.opis_zgloszenia)
        ```