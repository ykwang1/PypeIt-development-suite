from ech_fluxspec import *
#from ech_coadd import *
from pypeit.ech_coadd import *
from pypeit import fluxspec
import matplotlib.pyplot as plt
## test ech_fluxspec


def flux_single(debug=True,datapath='./',stdframe=None,sciframe=None,star_type='A0',star_mag=8.0,
                 ra=None, dec=None, std_file=None, BALM_MASK_WID=15., nresln=None,outfile=None):
    """
    test single frame
    :param debug:
    :return:
    """
    sens_dicts = ech_generate_sensfunc(datapath+stdframe,telluric=True, star_type=star_type,
                                       star_mag=star_mag,ra=ra, dec=dec, std_file = std_file,
                                       BALM_MASK_WID=BALM_MASK_WID, nresln=nresln,debug=debug)
    ech_save_master(sens_dicts, outfile=datapath+outfile)
    #sens_dicts = ech_load_master(datapath+'MasterSensFunc_NIRES.fits')
    sci_specobjs, sci_header = ech_load_specobj(datapath+sciframe)
    ech_flux_science(sci_specobjs,sens_dicts,sci_header,spectrograph=None)
    write_science(sci_specobjs, sci_header, datapath+sciframe[:-5]+'_FLUX.fits')
    return sens_dicts

def ech_flux_new(spectragraph='keck_nires',debug=False,datapath='./',star_type='A0',star_mag=8.6,BALM_MASK_WID=20.0,
                 norder=5,resolution=3000,polycorrect=True,polysens=False, objinfo='J1135_info.txt',
                 stdframe='spec1d_HIP53735_NIRES_2018Jun04T055220.216.fits'):
    """
    test NIRES with a list of files
    :return:
    """
    cat = np.genfromtxt(datapath+objinfo,dtype=str)
    filenames = cat[:,0]

    for i in range(len(filenames)):
        sciframe = datapath+filenames[i]

        FxSpec = fluxspec.EchFluxSpec(std_spec1d_file=datapath+stdframe,
                                      sci_spec1d_file=sciframe,
                                      spectrograph=spectragraph,
                                      telluric=True,
                                      sens_file=datapath+'sens_'+stdframe,
                                      star_type=star_type,
                                      star_mag=star_mag,
                                      BALM_MASK_WID = BALM_MASK_WID,
                                      resolution = resolution,
                                      polycorrect = polycorrect,
                                      polysens = polysens,
                                      norder = norder,
                                      debug=debug)
        if i==0:
            _ = FxSpec.generate_sensfunc()
            _ = FxSpec.save_master(FxSpec.sens_dict, outfile=datapath+'sens_'+stdframe)
        FxSpec.flux_science()
        FxSpec.write_science(sciframe[:-5]+'_flux.fits')


def ech_coadd_new(giantcoadd=False,debug=False,datapath='./',objinfo='J0252_objinfo.txt',qafile='ech_coadd',
                  outfile='J0910_GNIRS.fits',flux=True):

    cat = np.genfromtxt(datapath+objinfo,dtype=str)
    filenames = cat[:,0]
    scifiles = []
    for i in range(len(filenames)):
        filename = datapath+filenames[i]
        if flux:
            scifiles += [filename.replace('.fits','_flux.fits')]
        else:
            scifiles +=[filename]
    objids = cat[:,1]

    # Coadding
    kwargs={}
    spec1d = ech_coadd(scifiles, objids=objids,extract='OPT', flux=flux,giantcoadd=giantcoadd,
              wave_grid_method='velocity', niter=5,wave_grid_min=None, wave_grid_max=None, v_pix=None,
              scale_method='median', do_offset=False, sigrej_final=3.,
              do_var_corr=False, qafile=datapath+qafile, outfile=datapath+outfile, do_cr=True,debug=debug,**kwargs)
    return spec1d

def ech_load_xidl(files,extn=4,norder=6,order=None,extract='OPT',sensfile=None,AB=True):
    """
    ONLY tested for GNIRS for now
    files: A list of file names
    objid:
    norder:
    extract:
    flux:
    """

    nfiles = len(files)

    # Keywords for Table
    rsp_kwargs = {}
    rsp_kwargs['wave_tag'] = '{:s}_WAVE'.format(extract)
    rsp_kwargs['flux_tag'] = '{:s}_FLAM'.format(extract)
    rsp_kwargs['sig_tag'] = '{:s}_FLAM_SIG'.format(extract)

    # Reading magsens func
    if sensfile is not None:
        magfunc  = fits.getdata(sensfile, 0)
        loglams = fits.getdata(sensfile, 1)
        exptime = np.zeros(nfiles)
        for ii, fname in enumerate(files):
            exptime[ii] = fits.getheader(fname,0)['EXPTIME']

    # Load spectra
    spectra_list = []
    for ii, fname in enumerate(files):
        ext_final = fits.getdata(fname, -1)
        head_final = fits.getheader(fname,-1)
        if norder is None:
            if AB:
                norder = head_final['NAXIS2']/2
            else:
                norder = head_final['NAXIS2']
            msgs.info('spectrum {:s} has {:d} orders'.format(fname, norder))
        elif norder <=1:
            msgs.error('The number of orders have to be greater than one for echelle. Longslit data?')

        if AB:
            if order is None:
                msgs.info('Loading all orders into a gaint spectra')
                for iord in range(norder):
                    for aa in range(2):
                        wave = ext_final['WAVE_{:s}'.format(extract)][2 * iord + aa]
                        flux = ext_final['FLUX_{:s}'.format(extract)][2 * iord + aa]
                        sig = ext_final['SIG_{:s}'.format(extract)][2 * iord + aa]
                        if sensfile is not None:
                            magfunc1 = np.interp(np.log10(wave), loglams, magfunc[iord, :])
                            sensfunc = 10.0 ** (0.4 * magfunc1)
                            scale = sensfunc / exptime[ii]
                            flux = flux * scale
                            sig = sig * scale
                        spectrum = spec_from_array(wave, flux, sig, **rsp_kwargs)
                        # Append
                        spectra_list.append(spectrum)
            elif order >= norder:
                msgs.error('order number cannot greater than the total number of orders')
            else:
                for aa in range(2):
                    wave = ext_final['WAVE_{:s}'.format(extract)][2 * order + aa]
                    flux = ext_final['FLUX_{:s}'.format(extract)][2 * order + aa]
                    sig = ext_final['SIG_{:s}'.format(extract)][2 * order + aa]
                    if sensfile is not None:
                        magfunc1 = np.interp(np.log10(wave), loglams, magfunc[order, :])
                        sensfunc = 10.0 ** (0.4 * magfunc1)
                        scale = sensfunc / exptime[ii]
                        flux = flux * scale
                        sig = sig * scale
                    spectrum = spec_from_array(wave, flux, sig, **rsp_kwargs)
                    # Append
                    spectra_list.append(spectrum)
        else:
            if order is None:
                msgs.info('Loading all orders into a gaint spectra')
                for iord in range(norder):
                    wave = ext_final['WAVE_{:s}'.format(extract)][iord]
                    flux = ext_final['FLUX_{:s}'.format(extract)][iord]
                    sig = ext_final['SIG_{:s}'.format(extract)][iord]
                    if sensfile is not None:
                        magfunc1 = np.interp(np.log10(wave), loglams, magfunc[iord, :])
                        sensfunc = 10.0 ** (0.4 * magfunc1)
                        scale = sensfunc / exptime[ii]
                        flux = flux * scale
                        sig = sig * scale
                    spectrum = spec_from_array(wave, flux, sig, **rsp_kwargs)
                    # Append
                    spectra_list.append(spectrum)
            elif order >= norder:
                msgs.error('order number cannot greater than the total number of orders')
            else:
                wave = ext_final['WAVE_{:s}'.format(extract)][order]
                flux = ext_final['FLUX_{:s}'.format(extract)][order]
                sig = ext_final['SIG_{:s}'.format(extract)][order]
                if sensfile is not None:
                    magfunc1 = np.interp(np.log10(wave), loglams, magfunc[order, :])
                    sensfunc = 10.0 ** (0.4 * magfunc1)
                    scale = sensfunc / exptime[ii]
                    flux = flux * scale
                    sig = sig * scale
                spectrum = spec_from_array(wave, flux, sig, **rsp_kwargs)
                # Append
                spectra_list.append(spectrum)

    # Join into one XSpectrum1D object
    spectra = collate(spectra_list)
    # Return
    return spectra


def coadd_gnirs_xidl(giantcoadd=False,qafile='testgnirs',debug=False,datapath='./'):
    norder=6
    order = 0

    scifiles = [datapath+'/sci-cN20150707S0189-192.fits',
                datapath+'/sci-cN20150707S0193-196.fits',
                datapath+'/sci-cN20150707S0220-223.fits',
                datapath+'/sci-cN20150707S0224-223.fits']
    sensfile = datapath+'/HIP111538_0_sens.fits'
    if giantcoadd:
        spectra = ech_load_xidl(scifiles,extn=4,norder=norder,order=None,extract='OPT',sensfile=sensfile,AB=True)
        kwargs={}
        ech_kwargs = {'echelle': True, 'wave_grid_min': None, 'wave_grid_max': None}
        kwargs.update(ech_kwargs)
        # Coadding
        spec1d = coadd.coadd_spectra(spectra, wave_grid_method='velocity', niter=5,
                  scale_method='auto', do_offset=False, sigrej_final=3.,
                  do_var_corr=False, qafile=qafile, outfile=None, do_cr=True,debug=debug,**kwargs)
    else:
        msgs.info('Coadding individual orders first and then merge order')
        spectra_list = []
        # Keywords for Table
        extract='OPT'
        rsp_kwargs = {}
        rsp_kwargs['wave_tag'] = '{:s}_WAVE'.format(extract)
        rsp_kwargs['flux_tag'] = '{:s}_FLAM'.format(extract)
        rsp_kwargs['sig_tag'] = '{:s}_FLAM_SIG'.format(extract)
        wave_grid = np.zeros((2,norder))
        for iord in range(norder):
            spectra = ech_load_xidl(scifiles, extn=4, norder=norder, order=iord, extract='OPT', sensfile=sensfile,
                                    AB=True)
            kwargs = {}
            ech_kwargs = {'echelle': False, 'wave_grid_min': spectra.wvmin.value, 'wave_grid_max': spectra.wvmax.value, 'v_pix': None}
            wave_grid[0,iord] = spectra.wvmin.value
            wave_grid[1,iord] = spectra.wvmax.value
            kwargs.update(ech_kwargs)
            # Coadding the individual orders
            if qafile is not None:
                qafile_iord = qafile+'_%s'%str(iord)
            else:
                qafile_iord =  None
            spec1d_iord = coadd.coadd_spectra(spectra, wave_grid_method='velocity', niter=5,
                  scale_method='auto', do_offset=False, sigrej_final=3.,
                  do_var_corr=False, qafile=qafile_iord, outfile=None, do_cr=True,debug=debug,**kwargs)
            spectrum = spec_from_array(spec1d_iord.wavelength, spec1d_iord.flux, spec1d_iord.sig,**rsp_kwargs)
            spectra_list.append(spectrum)
        # Join into one XSpectrum1D object
        spectra_coadd = collate(spectra_list)
        kwargs['echelle'] = True
        kwargs['wave_grid_min'] = np.min(wave_grid)
        kwargs['wave_grid_max'] = np.max(wave_grid)
        spec1d = coadd.coadd_spectra(spectra_coadd, wave_grid_method='velocity', niter=5,
                  scale_method='auto', do_offset=False, sigrej_final=3.,
                  do_var_corr=False, qafile=qafile, outfile=None, do_cr=True,debug=debug,**kwargs)
    return spec1d,spectra_coadd,kwargs


def readgnirsxidl(filename):
    fitsfile = fits.open(filename)
    header = fitsfile[0].header
    wave, flux, error = fitsfile[2].data, fitsfile[0].data, fitsfile[1].data

    return wave, flux, error, header

def other_tests():
    # flux XSHOOTER
    datapath = '/Users/feige/Dropbox/PypeIt_DATA/XSHOOTER/J0439/NIR/Science/'
    stdframe = 'spec1d_STD,TELLURIC_XShooter_NIR_2018Oct08T232940.178.fits'
    sciframe = 'spec1d_STD,TELLURIC_XShooter_NIR_2018Oct08T233037.583.fits' # test fluxing with telluric star

    scilist = ['spec1d_J0439_XShooter_NIR_2018Oct09T063213.112.fits','spec1d_J0439_XShooter_NIR_2018Oct09T064021.266.fits',
               'spec1d_J0439_XShooter_NIR_2018Oct09T064829.420.fits','spec1d_J0439_XShooter_NIR_2018Oct09T065654.883.fits',
               'spec1d_J0439_XShooter_NIR_2018Oct09T070503.037.fits','spec1d_J0439_XShooter_NIR_2018Oct09T071311.193.fits']
    objids = ['OBJ0000','OBJ0000','OBJ0000','OBJ0001','OBJ0001','OBJ0001']
    star_mag = 5.644
    star_type = 'B9'
    outfile = 'HIP095619_XSHOOTER_NIR_SENS'

    flux_single(debug=False,datapath=datapath,stdframe=stdframe,sciframe=sciframe,
                star_type=star_type,star_mag=star_mag,BALM_MASK_WID=15., nresln=None,outfile=outfile)
    sci_specobjs, sci_header = ech_load_specobj(datapath + sciframe[:-5] + '_FLUX.fits')
    wavemask = sci_specobjs[13].optimal['WAVE']>1000.0*units.AA
    plt.plot(sci_specobjs[13].optimal['WAVE'][wavemask],sci_specobjs[13].optimal['FLAM'][wavemask])
    plt.show()

    sens_dicts = ech_generate_sensfunc(datapath + stdframe, telluric=True, star_type=star_type,
                                       star_mag=star_mag, ra=None, dec=None, std_file=None,
                                       BALM_MASK_WID=5.0, nresln=None, debug=True)
    ech_save_master(sens_dicts, outfile=datapath + outfile)


    scifiles = []
    for i in range(len(scilist)):
        sciframe = scilist[i]
        sci_specobjs, sci_header = ech_load_specobj(datapath + sciframe)
        ech_flux_science(sci_specobjs, sens_dicts, sci_header, spectrograph=None)
        write_science(sci_specobjs, sci_header, datapath + sciframe[:-5] + '_FLUX.fits')

        filename = datapath+sciframe
        scifiles += [filename.replace('.fits','_FLUX.fits')]

    # Coadding
    kwargs={}
    spec1d = ech_coadd(scifiles, objids=objids,extract='OPT', flux=True,giantcoadd=False,
              wave_grid_method='velocity', niter=5,wave_grid_min=None, wave_grid_max=None, v_pix=None,
              scale_method='median', do_offset=False, sigrej_final=3.,
              do_var_corr=False, qafile='test_xshooter.png', outfile=None, do_cr=True,debug=True,**kwargs)


    #Test GNIRS
    spec1d,spectra_coadd,kwargs = coadd_gnirs(giantcoadd=False,debug=True,datapath='/Users/feige/Dropbox/PypeIt_Redux/GNIRS/')
    wave, flux, error, header = readgnirsxidl('/Users/feige/Dropbox/PypeIt_Redux/GNIRS/PSO338+29_forpypeit.fits')
    cat = np.genfromtxt('/Users/feige/Dropbox/PypeIt_Redux/GNIRS/mods_spectrum_p338.txt')
    wave_opt, flux_opt, error_opt = cat[:, 0], cat[:, 1]/1e-17, cat[:, 2]/1e-17

    plt.figure(figsize=(12,4))
    plt.plot(wave_opt, flux_opt,'k-',label='MODS')
    plt.plot(wave,flux,'b-',label='XIDL')
    plt.plot(wave,error,'b-',alpha=0.5)
    plt.plot(spec1d.wavelength,spec1d.flux,'r-',label='PypeIt')
    plt.plot(spec1d.wavelength,spec1d.sig,'r-',alpha=0.5)
    plt.xlim([9000.,24800.])
    plt.ylim([-0.5,2.0])
    plt.legend(loc=1,fontsize=16)
    plt.show()


### 2018 Oct NIRES data reduction
#ech_flux_new(debug=True,datapath='/Users/feige/Work/Observations/NIRES/pypeit_redux/ut181001/Science/',\
#            objinfo='J0252_info.txt',stdframe='spec1d_HIP13917_V8p6_NIRES_2018Oct01T094225.598.fits',
#            star_type='A0',star_mag=8.6)
#coadd_nires(giantcoadd=False,debug=True,datapath='/Users/feige/Work/Observations/NIRES/pypeit_redux/ut181001/Science/',\
#           objinfo='J0252_info.txt')

### 2018 May GNIRS reduction
#ech_flux_new(debug=True,datapath='/Users/feige/Dropbox/PypeIt_Redux/GNIRS/ut180517/Science/',\
#            objinfo='J0910_info.txt',stdframe='spec1d_HIP43018_GNIRS_2018May16T225142.936.fits',
#            star_type='A0',star_mag=8.72)
#ech_coadd_new(giantcoadd=False,debug=True,datapath='/Users/feige/Dropbox/PypeIt_Redux/GNIRS/ut180517/Science/',
#              objinfo='J0910_info.txt',qafile='ech_coadd',outfile='J0910_GNIRS.fits')

#ech_flux_new(debug=True,datapath='/Users/feige/Dropbox/PypeIt_Redux/GNIRS/P006p39/Flux/',\
#            objinfo='tell_info.txt',stdframe='spec1d_A2VStar_GNIRS_2016Aug05T002219.142.fits',
#            star_type='A2',star_mag=6.688,norder=6,resolution=1000,BALM_MASK_WID=20.0,polycorrect=True,polysens=False)
#ech_coadd_new(giantcoadd=False,debug=True,datapath='/Users/feige/Dropbox/PypeIt_Redux/GNIRS/P006p39/Flux/',
#              objinfo='P006_info.txt',qafile='ech_coadd',outfile='P006_GNIRS.fits')

#ech_coadd_new(giantcoadd=False,debug=True,datapath='/Users/feige/Dropbox/OBS_DATA/GNIRS/ut190117/Science/',
#              objinfo='tell_info.txt',qafile='ech_coadd',outfile='spec1d_HIP61471_GNIRS_2019Jan17.fits',flux=False)
#ech_flux_new(debug=True,datapath='/Users/feige/Dropbox/OBS_DATA/GNIRS/ut190117/Science/',\
#            objinfo='tell_info.txt',stdframe='spec1d_HIP61471_GNIRS_2019Jan17T161602.759.fits',
#            star_type='A0',star_mag=7.275,BALM_MASK_WID=20.0,polycorrect=False)
#ech_coadd_new(giantcoadd=False,debug=True,datapath='/Users/feige/Dropbox/OBS_DATA/GNIRS/ut190117/Science/',
#              objinfo='tell_info.txt',qafile='ech_coadd',outfile='spec1d_HIP61471_GNIRS_2019Jan17.fits',flux=True)
### XSHOOTER
#ech_flux_new(debug=True,datapath='/Users/feige/Dropbox/PypeIt_DATA/XSHOOTER/J0439/NIR/Science/',\
#            objinfo='J0439_info.txt',stdframe='spec1d_STD,TELLURIC_XShooter_NIR_2018Oct08T232940.178.fits',
#            star_type='A0',star_mag=5.644)
#ech_coadd_new(giantcoadd=False,debug=True,datapath='/Users/feige/Dropbox/PypeIt_DATA/XSHOOTER/J0439/NIR/Science/',
#              objinfo='J0439_info.txt',qafile='ech_coadd',outfile='J0439_XSHOOTER.fits')

#ech_flux_new(debug=False,datapath='/Users/feige/Dropbox/PypeIt_Redux/XSHOOTER/J0020m3653/VIS/Science/',\
#            objinfo='J0020_info.txt',stdframe='spec1d_STD,TELLURIC_XShooter_VIS_2017Oct26T015817.881.fits',
#            star_type='B7',star_mag=5.812,norder=5,resolution=8000,BALM_MASK_WID=20.0,polycorrect=True,polysens=False)
#ech_coadd_new(giantcoadd=False,debug=False,datapath='/Users/feige/Dropbox/PypeIt_Redux/XSHOOTER/J0020m3653/VIS/Science/',
#              objinfo='J0020_info.txt',qafile='ech_coadd',outfile='J0020_XSHOOTER.fits')

## Old laptop
#ech_flux_new(debug=False,datapath='/Users/feige/Work2018/XSHOOTER/J1048m0109/VIS/Science/',\
#            objinfo='J1048_info.txt',stdframe='spec1d_STD,TELLURIC_XShooter_VIS_2017Feb02T050605.546.fits',
#            star_type='B9',star_mag=7.01,norder=5,resolution=8000,BALM_MASK_WID=20.0,polycorrect=True,polysens=False)
#ech_coadd_new(giantcoadd=False,debug=False,datapath='/Users/feige/Work2018/XSHOOTER/J1048m0109/VIS/Science/',
#              objinfo='J1048_info.txt',qafile='ech_coadd',outfile='J1048_XSHOOTER.fits')