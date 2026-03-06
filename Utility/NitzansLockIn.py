# -*- coding: utf-8 -*-
"""
Created on Wed Feb 11 13:52:16 2026

@author: QMR
"""
from pymeasure.instruments.srs import SR830
import pyvisa  # Visa handles communication with instruments
from time import sleep
from pymeasure.adapters import VISAAdapter

class LOCKIN():
    def connect_lock_in(self,autogain,freq=668.4):
        '''
        connects lock-in with improved initialization and error handling
    
        Parameters
        ----------
        autogain : bool
            Whether to perform autogain on startup, recommended.
        freq : float
            Operating frequency in Hz
    
        Returns
        -------
        None.
    
        '''
        try:
            adapter = VISAAdapter("GPIB0::8::INSTR", encoding="latin-1")  # disable ASCII decoding
            self.LI = SR830("GPIB0::8::INSTR")
            
            # Allow extra time for connection to stabilize
            sleep(1)
            
            # Clear any pending data from initialization
            self._clear_LI_buffer(max_attempts=2)
            
            # Set basic configuration
            self._safe_property_set('reference_source', "Internal")
            self._safe_property_set('frequency', freq)
            
            # Wait for frequency to stabilize
            sleep(1)
            
            # Set output voltage
            self._safe_property_set('sine_voltage', self.LI_output_voltage)
            
            # Perform autogain if requested
            if autogain:
                if not self._safe_auto_gain_wrapper(timeout=30):
                    print("Warning: Auto-gain failed during initialization, continuing anyway")
            
            sleep(2)
            
            # Verify connection is working with a test query
            try:
                test_response = self._synced_ask("*IDN?", retries=2)
                if not test_response:
                    raise ConnectionError("Lock-in test query returned empty")
            except Exception as e:
                self.disconnect()
                raise ConnectionError(f"Failed to verify lock-in connection: {e}")
            
            self.lock_in_connected = True
            print("Lock-in amplifier connected and initialized successfully")
            
        except Exception as e:
            self.disconnect()
            raise ConnectionError(f"Failed to connect Lock-In: {e}")
    def _clear_LI_buffer(self, max_attempts=3):
        """
        Aggressively clear the SR830 buffer by reading and discarding any pending data.
        
        Parameters
        ----------
        max_attempts : int
            Maximum number of read attempts to clear buffer.
        
        Returns
        -------
        None
        """
        for attempt in range(max_attempts):
            try:
                # Set a short timeout for clearing operations
                original_timeout = self.LI.adapter.connection.timeout
                self.LI.adapter.connection.timeout = 100  # 100ms timeout
                try:
                    # Try to read any pending data without blocking
                    _ = self.LI.read()
                except:
                    # Timeout or no data available is expected
                    pass
                finally:
                    self.LI.adapter.connection.timeout = original_timeout
                break
            except Exception:
                if attempt == max_attempts - 1:
                    raise
                sleep(0.05)
    
    def _synced_ask(self, cmd, retries=3, wait_after_write=0.05):
        """
        Perform a synchronized query with proper buffer clearing and retry logic.
        
        This method ensures that:
        1. The command buffer is clear before sending
        2. The device has time to process the command
        3. The response is not contaminated with previous data
        
        Parameters
        ----------
        cmd : str
            SCPI command to send
        retries : int
            Number of retries if query fails
        wait_after_write : float
            Time to wait after writing command (seconds)
        
        Returns
        -------
        str
            The response from the device
        
        Raises
        ------
        Exception
            If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(retries):
            try:
                # Clear any pending data in the buffer
                self._clear_LI_buffer(max_attempts=2)
                
                # Write the command and wait for device to process
                self.LI.write(cmd)
                sleep(wait_after_write)
                
                # Read the response
                response = self.LI.read()
                return response.strip()
                
            except Exception as e:
                last_exception = e
                # Exponential backoff: wait longer between retries
                sleep(0.1 * (2 ** attempt))
                
                # Try to recover by clearing buffer again
                try:
                    self._clear_LI_buffer(max_attempts=1)
                except:
                    pass
        
        # All retries failed
        raise last_exception if last_exception else Exception(f"Failed to execute command: {cmd}")
    
    def _safe_property_set(self, property_name, value, retries=2):
        """
        Safely set a SR830 property with verification and retry.
        
        Parameters
        ----------
        property_name : str
            Name of the property (e.g., 'frequency', 'sine_voltage')
        value : float or int
            Value to set
        retries : int
            Number of retries on failure
        
        Returns
        -------
        bool
            True if set successfully, False otherwise
        """
        for attempt in range(retries):
            try:
                setattr(self.LI, property_name, value)
                # Small delay to allow the setting to propagate
                sleep(0.1)
                # Optionally verify by reading back (comment out if too slow)
                # actual_value = getattr(self.LI, property_name)
                return True
            except Exception as e:
                if attempt < retries - 1:
                    sleep(0.2 * (2 ** attempt))
                    # Try to recover
                    try:
                        self._clear_LI_buffer(max_attempts=1)
                    except:
                        pass
                else:
                    print(f"Failed to set {property_name} to {value}: {e}")
                    return False
        return False
    
    def _safe_auto_gain_wrapper(self, timeout=30):
        """
        Wrapper around auto_gain() with better error handling and timeout.
        
        Parameters
        ----------
        timeout : int
            Maximum time to wait for autogain to complete (seconds)
        
        Returns
        -------
        bool
            True if autogain succeeded, False otherwise
        """
        try:
            original_timeout = self.LI.adapter.connection.timeout
            self.LI.adapter.connection.timeout = timeout * 1000  # Convert to ms
            
            try:
                # Clear buffer before autogain
                self._clear_LI_buffer(max_attempts=1)
                self.LI.auto_gain()
                sleep(2)  # Short settle; further waits handled by caller if needed
                return True
            finally:
                self.LI.adapter.connection.timeout = original_timeout
                
        except Exception as e:
            print(f"Auto-gain failed: {e}")
            return False
    
    def LI_query_output(self, output_index, retries=3):
        """
        Query SR830 output channel with robust error handling.
        
        Parameters
        ----------
        output_index : int
            Output channel (1-4: X, Y, R, theta)
        retries : int
            Number of retries
        
        Returns
        -------
        float
            The queried value
        
        Raises
        ------
        Exception
            If query fails after all retries
        """
        return float(self._synced_ask(f"OUTP? {output_index}", retries=retries))
    
    def LI_safe_query(self, query="magnitude"):
        """
        Improved safe query for lock-in measurements with automatic recovery.
        
        Parameters
        ----------
        query : str
            'magnitude' (R), 'theta', 'x', or 'y'
        
        Returns
        -------
        float
            The queried measurement value
        """
        query_map = {
            'magnitude': 3,  # R
            'theta': 4,      # theta
            'x': 1,          # X
            'y': 2           # Y
        }
        
        if query not in query_map:
            print(f"Unrecognized query: {query}")
            return None
        
        output_index = query_map[query]
        
        try:
            # First attempt with standard retry
            return self.LI_query_output(output_index, retries=2)
        except Exception as first_error:
            # If first attempt fails, try recovery sequence
            try:
                print(f"First query attempt failed for {query}, attempting recovery... temperature {self.temperature}")
                sleep(0.5)
                # Read any pending data
                try:
                    self.LI.read()
                except:
                    pass
                sleep(0.2)
                # Retry after recovery
                return self.LI_query_output(output_index, retries=1)
            except Exception as recovery_error:
                # As last resort, try clearing and reading raw
                try:
                    self._clear_LI_buffer(max_attempts=2)
                    sleep(0.3)
                    return self.LI_query_output(output_index, retries=1)
                except:
                    self.disconnect()
                    raise RuntimeError(f"Failed to query {query} after recovery attempts")

    def LI_overload_flags(self):
        """
        Return SR830 overload flags as a dict.

        The SR830 returns a bitfield from the LIAS? query:
        bit0=input, bit1=filter, bit2=output, bit3=dynamic reserve overload.
        """
        status = int(self._synced_ask("LIAS?", retries=2))
        return {
            "input_overload": bool(status & (1 << 0)),
            "filter_overload": bool(status & (1 << 1)),
            "output_overload": bool(status & (1 << 2)),
            "dynamic_reserve_overload": bool(status & (1 << 3)),
        }

    def _adjust_sensitivity_if_overloaded(self, max_steps=2):
        """
        Quickly relieve overload by stepping sensitivity coarser without full auto_gain.

        Parameters
        ----------
        max_steps : int
            Maximum number of sensitivity steps to move in one call.

        Returns
        -------
        bool
            True if sensitivity was adjusted, False otherwise.
        """
        try:
            flags = self.LI_overload_flags()
            if not any(flags.values()):
                return False

            sens_list = self.LI.SENSITIVITIES
            current = self.LI.sensitivity
            idx = sens_list.index(current)
            # Overload -> move to less sensitive (higher index) setting
            target_idx = min(idx + max_steps, len(sens_list) - 1)
            if target_idx != idx:
                self._safe_property_set('sensitivity', sens_list[target_idx])
                sleep(0.2)  # allow change to settle briefly
                return True
        except Exception as e:
            print(f"Sensitivity adjust skip due to error: {e}")
        return False